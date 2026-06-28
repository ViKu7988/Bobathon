"""
Regulatory Radar — Main Flask Application
EcoComply | IBM Bobathon 2025
"""

from flask import Flask
from flask_cors import CORS
from routes.regulations import regulations_bp
from routes.partners    import partners_bp
from routes.alerts      import alerts_bp
from routes.pipeline    import pipeline_bp
from routes.upload      import upload_bp
from routes.findings    import findings_bp
from config import Config
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Register blueprints
    app.register_blueprint(regulations_bp, url_prefix="/api/regulations")
    app.register_blueprint(partners_bp,    url_prefix="/api/partners")
    app.register_blueprint(alerts_bp,      url_prefix="/api/alerts")
    app.register_blueprint(pipeline_bp,    url_prefix="/api/pipeline")
    app.register_blueprint(upload_bp,      url_prefix="/api/upload")
    app.register_blueprint(findings_bp,    url_prefix="/api/findings")

    @app.route("/api/health")
    def health():
        return {"status": "ok", "service": "Regulatory Radar API", "version": "1.0.0"}

    logger.info("Regulatory Radar API started")
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
