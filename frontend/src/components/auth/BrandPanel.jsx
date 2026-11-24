function BrandPanel() {
  return (
    <aside className="brand-panel" aria-label="Presentación de Kaanbal">
      <div className="brand-grid" />
      <div className="brand-orbit brand-orbit-one" />
      <div className="brand-orbit brand-orbit-two" />

      <div className="brand-content">
        <div className="brand-mark" aria-hidden="true">
          <span>K</span>
        </div>
        <div>
          <p className="brand-eyebrow">Aprende matemáticas</p>
          <h1>Kaanbal</h1>
          <p className="brand-description">
            Convierte cada problema en una oportunidad para entender,
            practicar y avanzar.
          </p>
        </div>
      </div>

      <div className="brand-proof">
        <span className="brand-proof-dot" />
        Tu progreso, siempre contigo
      </div>
    </aside>
  )
}

export default BrandPanel
