from fastapi import FastAPI


def initialize_health_endpoints(app: FastAPI):
    # TODO: grow this with more more options tied to settings and level of health information
    #   - provide db connection health / status
    #   - provide interface status (i.e. discord bot status)
    #   - provide scheduler status

    @app.get("/health", tags=["System"])
    def healthy() -> str:
        """Health check route."""
        return "Healthy"
