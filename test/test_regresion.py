"""Pruebas sin Bedrock. Ejecuta desde la raíz: python -m tests.test_regresion"""
import json
import sys
import types

# Permite correr las pruebas aunque boto3/dotenv no estén instalados.
for name, attrs in {
    "botocore": {}, "botocore.exceptions": {"ClientError": Exception},
    "boto3": {"client": lambda *a, **k: None},
    "dotenv": {"load_dotenv": lambda: None},
}.items():
  if name not in sys.modules:
    try:
      __import__(name)
    except ImportError:
      module = types.ModuleType(name)
      module.__dict__.update(attrs)
      sys.modules[name] = module

from app.ai.evaluator import _normalize_evaluation, _sanitize, evaluate_student
from app.core.answer_validator import find_arithmetic_slips, validate_linear_answer
from app.core.diagnostic import DIAGNOSTIC_ITEMS, set_diagnostic_item
from app.core.pedagogical_engine import build_profile, update_pedagogical_state
from app.core.state import PedagogicalState
import main


def test_validator():
  assert validate_linear_answer("x = 15/3, x = 5", 5).status == "correct"
  assert validate_linear_answer("pues x = 5 por q divides", 5).status == "correct"
  assert validate_linear_answer("x = 45", 5).status == "incorrect"
  assert validate_linear_answer("5", 5).status == "correct"
  assert validate_linear_answer("5, por q 3*5 es 15", 5).status == "unrecognized"


def test_arithmetic_checker():
  assert find_arithmetic_slips("5, por q 3*5 es 15") == []
  assert find_arithmetic_slips("lo intente comprobar, si 3 * 45 es 15") == []
  assert find_arithmetic_slips("si multiplico cambos por 3 es 5 * 3 = 3 * 5") == []
  assert find_arithmetic_slips("x = 6/2 = 3") == []
  assert find_arithmetic_slips("entonces 2*3 = 7") == ["2*3 = 7"]


def test_quotes_and_final_answer_filtered():
  raw = {
      "student_intent": "giving_answer",
      "final_answer": {"value": "5", "quote": "5, por q"},
      "dimensions": {
          "procedural": {"level": "strong", "quote": "3*5 es 15"},
          "conceptual": {"level": "strong", "quote": "frase inventada"},
      },
      "errors": [{"label": "sign_error", "quote": "no está"},
                 {"label": "arithmetic_slip", "quote": "3*5 es 15"}],
  }
  ev = _sanitize(_normalize_evaluation(raw), "5, por q 3*5 es 15")
  assert ev["final_answer"] == 5.0
  assert ev["dimensions"]["procedural"]["level"] == "strong"
  assert ev["dimensions"]["conceptual"]["level"] == "not_observed"
  assert ev["errors"] == []  # el LLM no puede reportar aritmética


def test_evaluator_fallback_when_not_json():
  class Chatty:
    calls = 0
    def converse(self, **kw):
      Chatty.calls += 1
      return {"output": {"message": {"content": [{"text": "Claro, te explico..."}]}}}
  conv = [{"role": "user", "content": [{"text": "pero ya te dije"}]}]
  ev = evaluate_student(Chatty(), "m", conv, PedagogicalState(), "pero ya te dije", "q")
  assert ev["evaluator_failed"] and Chatty.calls == 2


def fake_eval(proc, conc, quote, errors=(), conc_label=None):
  return _sanitize(_normalize_evaluation({
      "student_intent": "giving_answer",
      "dimensions": {
          "procedural": {"level": proc, "quote": quote},
          "conceptual": {"level": conc, "quote": quote},
          "relational": {"level": "not_observed", "quote": ""},
      },
      "errors": [{"label": l, "quote": quote} for l in errors],
  }), quote)


def test_confidence_grows_and_hypothesis_dies():
  state = PedagogicalState()
  set_diagnostic_item(state, DIAGNOSTIC_ITEMS[0])
  update_pedagogical_state(state, fake_eval("weak", "none", "x = 45", ["wrong_inverse_operation"]), None)
  assert state.hypotheses["wrong_inverse_operation"].status == "active"
  assert state.procedural.confidence < 0.4
  for _ in range(3):
    update_pedagogical_state(state, fake_eval("strong", "partial", "x = 5 porque dividí"), None)
  assert state.hypotheses["wrong_inverse_operation"].status == "refuted"


def test_rule_without_reason_is_refuted_by_conceptual_evidence():
  state = PedagogicalState()
  update_pedagogical_state(state, fake_eval("strong", "weak", "paso el 4 al otro lado", ["rule_without_reason"]), None)
  assert state.hypotheses["rule_without_reason"].status == "active"
  for _ in range(4):
    update_pedagogical_state(state, fake_eval("strong", "strong", "divido ambos lados porque se mantiene la igualdad"), None)
  assert state.hypotheses["rule_without_reason"].status == "refuted"
  assert not state.exercise_solved  # nada se marca resuelto en diagnóstico


def test_full_flow_with_fake_bedrock():
  tutor_histories = []

  class FakeClient:
    def converse(self, modelId, system, messages, inferenceConfig):
      if "evaluador" in system[0]["text"]:
        text = messages[-1]["content"][0]["text"].split("<<<\n")[1].split("\n>>>")[0]
        body = {
            "student_intent": "giving_answer",
            "final_answer": {"value": "5" if "5" in text else "3", "quote": text} if any(c in text for c in "35") else {"value": None},
            "dimensions": {
                "procedural": {"level": "strong", "quote": text},
                "conceptual": {"level": "partial", "quote": text},
                "relational": {"level": "not_observed", "quote": ""},
            },
            "errors": [], "strategies_used": ["inverse_operation"],
        }
        out = json.dumps(body)
      else:
        tutor_histories.append(messages)
        out = "Respuesta del tutor"
      return {"output": {"message": {"content": [{"text": out}]}}}

  main.boto3.client = lambda *a, **k: FakeClient()
  state, conv = PedagogicalState(), []
  set_diagnostic_item(state, DIAGNOSTIC_ITEMS[0])
  for a in ["5, por q 3*5 es 15", "primero resto 4 y x = 3", "el 45 está mal", "ambos lados valen lo mismo"]:
    main.process_student_message(a, "m", "r", conv, state)
  assert state.phase == "practice" and state.active_exercise_id == "eq_003" or state.active_exercise_id
  assert state.learning_evidence[0]["validation"] == "correct"  # "5, por q..." ya se valida
  assert state.active_exercise_id == "eq_003"  # procedimiento fuerte => arranca en nivel 2
  reply = main.process_student_message("2x = 6, divido ambos lados por 2, x = 3", "m", "r", conv, state)
  history = tutor_histories[-1]
  assert len(history) == 1 and history[0]["role"] == "user"  # sin el diagnóstico
  assert state.active_exercise_statement.split(":")[-1].strip() in reply  # red de seguridad


if __name__ == "__main__":
  for name, fn in list(globals().items()):
    if name.startswith("test_"):
      fn()
      print("OK", name)