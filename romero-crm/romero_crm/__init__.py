import warnings

# El Python que trae macOS usa LibreSSL: urllib3 avisa, pero las conexiones HTTPS funcionan igual.
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

APP_NAME = "Romero CRM"
APP_VERSION = "1.0.0"
