"""Custom OpenSpoolMan entry point; keeps local extensions outside upstream app.py."""
from app import app
from bambu_auth_routes import bp as bambu_cloud_bp

app.secret_key = app.secret_key or "openspoolman-local-bambu-cloud"
app.register_blueprint(bambu_cloud_bp)

if __name__ == "__main__":
    app.run(debug=True)
