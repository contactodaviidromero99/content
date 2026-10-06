import warnings

# El Python que trae macOS usa LibreSSL: urllib3 avisa, pero las conexiones HTTPS funcionan igual.
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

APP_NAME = "Romero Xandre CRM"
APP_SHORT = "Romero Xandre"
APP_VERSION = "2.0.0"
# La carpeta de datos conserva el nombre de siempre para no perder el historial al actualizar.
DATA_FOLDER = "Romero CRM"
