#!/bin/bash
cd "$(dirname "$0")" || exit 1
clear
echo ""
echo "  Romero CRM se está abriendo…"
echo "  La primera vez tarda 1-2 minutos porque prepara lo que necesita."
echo "  Puedes minimizar esta ventana. Para salir, cierra la ventana de Romero CRM."
echo ""
exec /bin/bash ./scripts/run.sh "$@"
