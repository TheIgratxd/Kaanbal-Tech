import http from "node:http";

const port = Number(process.env.PORT ?? 3000);

const server = http.createServer((_request, response) => {
  response.statusCode = 200;
  response.setHeader("Content-Type", "application/json");
  response.end(JSON.stringify({ status: "ok", service: "backend" }));
});

server.listen(port, "0.0.0.0", () => {
  console.log(`Backend listening on port ${port}`);
});