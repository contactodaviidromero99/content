#!/bin/bash
cd "$(dirname "$0")" || exit 1
clear
echo ""
echo "  Romero Xandre CRM se está abriendo…"
echo "  La primera vez tarda 1-2 minutos porque prepara lo que necesita."
echo "  Puedes minimizar esta ventana. Para salir, cierra la ventana de Romero Xandre CRM."
echo ""
exec /bin/bash ./scripts/run.sh "$@"
