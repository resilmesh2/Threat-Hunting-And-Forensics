#!/bin/bash

DASHBOARDS_URL="http://192.168.200.141:5601" # opensearch use port 5601 to work with saved objective files
AUTH_HEADER="username:password"  # Update if needed
NOTEBOOKS="notebooks.ndjson"
VIZDASH="vizdash.ndjson"

#  Import Saved Objects
echo "Importing saved objects..."
curl -v -k -u "$AUTH_HEADER" -X POST "$DASHBOARDS_URL/api/saved_objects/_import?overwrite=true" \
  -H "osd-xsrf: true" \
  --form file=@"$NOTEBOOKS"


echo "Importing saved objects..."
curl -v -k -u "$AUTH_HEADER" -X POST "$DASHBOARDS_URL/api/saved_objects/_import?overwrite=true" \
  -H "osd-xsrf: true" \
  --form file=@"$VIZDASH"

echo "Installation completed successfully."