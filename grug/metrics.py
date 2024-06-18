from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator, PrometheusFastApiInstrumentator
from starlette.responses import Response

from grug.settings import settings

instrumentor: PrometheusFastApiInstrumentator | None = None

# NOTE: docs on creating custom application metrics here:
# https://github.com/trallnag/prometheus-fastapi-instrumentator?tab=readme-ov-file#creating-new-metrics


def initialize_metrics(app: FastAPI):
    if settings.enable_metrics_endpoint:

        global instrumentor
        instrumentor = Instrumentator().instrument(app)

        @app.get("/metrics", tags=["System"])
        async def metrics_endpoint(key: str | None = None):
            # Check if the metrics_key is set and if the key is correct
            if settings.metrics_key and key != settings.metrics_key.get_secret_value():
                # TODO: ship unauthorized login attempts to an auth log file so that if/when fail2ban is setup it can
                #       capture and ban the offending IP address.  might make the most sense to make a middleware that
                #       logs these when a 401 is returned from any endpoint.
                return Response(status_code=401)

            # Generate the metrics response
            resp = Response(content=generate_latest(instrumentor.registry))
            resp.headers["Content-Type"] = CONTENT_TYPE_LATEST
            return resp
