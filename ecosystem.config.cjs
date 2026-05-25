module.exports = {
  apps: [
    {
      name: "data-oop-api",
      cwd: "/Users/tallpizza/project/data-oop",
      script: "uv",
      args: "run uvicorn server.api:app --host 0.0.0.0 --port 8001 --reload",
      interpreter: "none",
      autorestart: true,
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    },
    {
      name: "data-oop-ui",
      cwd: "/Users/tallpizza/project/data-oop/ui",
      script: "npm",
      args: "run dev -- --host 0.0.0.0 --port 5173",
      interpreter: "none",
      autorestart: true,
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
    }
  ]
}
