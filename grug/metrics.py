from fastapi import FastAPI
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator, PrometheusFastApiInstrumentator
from starlette.responses import Response

instrumentor: PrometheusFastApiInstrumentator | None = None

# TODO: create custom metrics here
#   - https://github.com/trallnag/prometheus-fastapi-instrumentator?tab=readme-ov-file#creating-new-metrics


def initialize_metrics(app: FastAPI):
    global instrumentor
    instrumentor = Instrumentator().instrument(app)

    # TODO: enable auth on this endpoint either with an API key or basic auth or something, but it needs to work
    #       natively with. might make most sense to have a key in as a query param, not the most secure, but that way
    #       you can still hook up anything that scrapes prometheus metrics to it with just a url.
    @app.get("/metrics", tags=["System"])
    async def metrics_endpoint():
        resp = Response(content=generate_latest(instrumentor.registry))
        resp.headers["Content-Type"] = CONTENT_TYPE_LATEST
        return resp
