#!/bin/sh
set -e

# 1. Determine the Primary/Backup Roles
if [ "$ACTIVE_POOL" = "blue" ]; then
    export UPSTREAM_BLUE_ROLE=""
    export UPSTREAM_GREEN_ROLE="backup"
    echo "Configuration: Blue Primary / Green Backup"
elif [ "$ACTIVE_POOL" = "green" ]; then
    export UPSTREAM_BLUE_ROLE="backup"
    export UPSTREAM_GREEN_ROLE=""
    echo "Configuration: Green Primary / Blue Backup"
else
    echo "Error: ACTIVE_POOL not set. Exiting."
    exit 1
fi

# 2. Substitute Variables into the Template
envsubst "\$UPSTREAM_BLUE_ROLE \$UPSTREAM_GREEN_ROLE \$PORT \$ACTIVE_POOL \$RELEASE_ID" < /etc/nginx/conf.d/nginx.conf.template > /etc/nginx/conf.d/default.conf

echo "Nginx configuration generated successfully."

# 3. Execute Nginx
exec nginx -g 'daemon off;'