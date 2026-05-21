#!/bin/bash
# install-trishul-snmp-suite-v1.4.1.sh - Deploy the pinned Trishul SNMP Suite 1.4.1 image
# Usage: ./install-trishul-snmp-suite-v1.4.1.sh <command> [--platform PLATFORM] [--image IMAGE]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

GHCR_USER="tosumitdhaka"
PINNED_APP_VERSION="1.4.1"
APP_GHCR_IMAGE="ghcr.io/${GHCR_USER}/trishul-snmp-suite:${PINNED_APP_VERSION}"
APP_IMAGE="$APP_GHCR_IMAGE"
CONTAINER_NAME="trishul-snmp"
VOLUME_NAME="trishul-snmp-data"
LEGACY_CONTAINER_BACKEND="trishul-snmp-backend"
LEGACY_CONTAINER_FRONTEND="trishul-snmp-frontend"
LEGACY_VOLUME_NAME="trishul-snmp-data"

APP_PORT="${APP_PORT:-${FRONTEND_PORT:-8081}}"
BACKEND_COMPAT_PORT="${BACKEND_PORT:-}"
SNMP_PORT="${SNMP_PORT:-2161}"
TRAP_PORT="${TRAP_PORT:-2162}"
IMAGE_SOURCE="${TRISHUL_IMAGE_SOURCE:-ghcr}"
IMAGE_OVERRIDE="${TRISHUL_IMAGE:-}"
DOCKER_PLATFORM="${DOCKER_PLATFORM:-${TRISHUL_DOCKER_PLATFORM:-}}"
SKIP_LEGACY_MIGRATION="${TRISHUL_SKIP_LEGACY_MIGRATION:-0}"
COMMAND="up"
POSITIONAL_ARGS=()
RESTORE_FILE=""

RUNTIME_APP_NAME="${APP_NAME:-Trishul SNMP Suite}"
RUNTIME_APP_AUTHOR="${APP_AUTHOR:-Sumit Dhaka}"
RUNTIME_APP_DESCRIPTION="${APP_DESCRIPTION:-Professional SNMP Simulation Tool}"
RUNTIME_SESSION_TIMEOUT="${SESSION_TIMEOUT:-3600}"
RUNTIME_SNMP_COMMUNITY="${SNMP_COMMUNITY:-public}"
RUNTIME_AUTO_START_SIMULATOR="${AUTO_START_SIMULATOR:-true}"
RUNTIME_AUTO_START_TRAP_RECEIVER="${AUTO_START_TRAP_RECEIVER:-true}"
RUNTIME_MIB_AUTO_FETCH="${MIB_AUTO_FETCH:-false}"
RUNTIME_WS_INTERNAL_PORT="${WS_INTERNAL_PORT:-19876}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
ENV_ARGS=()

if [ -f "$ENV_FILE" ]; then
    ENV_ARGS+=(--env-file "$ENV_FILE")
fi

fail() {
    echo -e "${RED}Error: $*${NC}" >&2
    exit 1
}

normalize_platform() {
    case "${1:-}" in
        "")
            ;;
        linux/*)
            printf '%s\n' "$1"
            ;;
        amd64|arm64)
            printf 'linux/%s\n' "$1"
            ;;
        *)
            printf '%s\n' "$1"
            ;;
    esac
}

docker_platform_args() {
    if [ -n "$DOCKER_PLATFORM" ]; then
        printf '%s\n' --platform "$DOCKER_PLATFORM"
    fi
}

skip_legacy_migration_requested() {
    case "${SKIP_LEGACY_MIGRATION,,}" in
        1|true|yes|on)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

image_uses_ghcr() {
    case "$APP_IMAGE" in
        ghcr.io/*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

refresh_app_image() {
    case "$IMAGE_SOURCE" in
        ghcr|cached)
            ;;
        *)
            fail "Unsupported image source '$IMAGE_SOURCE'. Use 'ghcr' or 'cached'."
            ;;
    esac

    if [ -n "$IMAGE_OVERRIDE" ]; then
        APP_IMAGE="$IMAGE_OVERRIDE"
    else
        APP_IMAGE="$APP_GHCR_IMAGE"
    fi
}

set_image_source() {
    case "$1" in
        ghcr|cached)
            IMAGE_SOURCE="$1"
            refresh_app_image
            ;;
        *)
            fail "Unsupported image source '$1'. Use 'ghcr' or 'cached'."
            ;;
    esac
}

parse_cli_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --image)
                [ $# -ge 2 ] || fail "--image requires a value."
                IMAGE_OVERRIDE="$2"
                shift 2
                ;;
            --platform)
                [ $# -ge 2 ] || fail "--platform requires a value."
                DOCKER_PLATFORM="$2"
                shift 2
                ;;
            --no-migrate)
                SKIP_LEGACY_MIGRATION=1
                shift
                ;;
            --help|-h|help)
                COMMAND="help"
                shift
                ;;
            --)
                shift
                while [ $# -gt 0 ]; do
                    POSITIONAL_ARGS+=("$1")
                    shift
                done
                ;;
            -*)
                fail "Unknown option '$1'."
                ;;
            *)
                POSITIONAL_ARGS+=("$1")
                shift
                ;;
        esac
    done
}

validate_command_args() {
    if [ "$COMMAND" = "restore" ]; then
        if [ ${#POSITIONAL_ARGS[@]} -gt 1 ]; then
            fail "restore accepts only one backup filename."
        fi
        RESTORE_FILE="${POSITIONAL_ARGS[0]:-}"
        return 0
    fi

    if [ ${#POSITIONAL_ARGS[@]} -gt 0 ]; then
        fail "Unexpected argument(s): ${POSITIONAL_ARGS[*]}"
    fi
}

show_usage() {
    echo "Usage: $0 <command> [--platform PLATFORM] [--image IMAGE] [--no-migrate]"
    echo ""
    echo "This script is pinned to the published Trishul SNMP Suite 1.4.1 image."
    echo "It keeps the legacy runtime names: container '${CONTAINER_NAME}' and volume '${VOLUME_NAME}'."
    echo "Its default ports are shifted so it can run beside the 2.0 installer."
    echo "Use --platform to select a specific manifest when pulling or running the pinned tag."
    echo ""
    echo "Commands:"
    echo "  up             - Pull the selected pinned image and start it"
    echo "  up-cached      - Start the selected pinned image using the already-pulled local copy"
    echo "  down           - Stop and remove current or legacy containers"
    echo "  restart        - Stop then pull and restart the pinned 1.4.1 container"
    echo "  restart-cached - Stop then restart from the already-pulled pinned image"
    echo "  pull           - Pull the pinned image only"
    echo "  logs           - Tail suite container logs"
    echo "  status         - Show container status, image, volume, and live app version"
    echo "  backup         - Backup the data volume to tar.gz"
    echo "  restore        - Restore data from backup"
    echo ""
    echo "CLI options:"
    echo "  --platform PLATFORM - Docker platform override, for example linux/amd64 or linux/arm64"
    echo "  --image IMAGE       - Override the image reference to pull or run"
    echo "  --no-migrate        - Skip automatic copy from legacy volume ${LEGACY_VOLUME_NAME}"
    echo ""
    echo "Environment variables:"
    echo "  APP_PORT                - Canonical app port (default: FRONTEND_PORT or 8081)"
    echo "  FRONTEND_PORT           - Legacy alias for APP_PORT"
    echo "  BACKEND_PORT            - Optional compatibility port mapped to the same app"
    echo "  SNMP_PORT               - SNMP UDP port (default: 2161)"
    echo "  TRAP_PORT               - Trap receiver UDP port (default: 2162)"
    echo "  GHCR_TOKEN              - GitHub PAT for GHCR if needed"
    echo "  TRISHUL_IMAGE_SOURCE    - ghcr or cached (default: ghcr)"
    echo "  TRISHUL_IMAGE           - Image reference override"
    echo "  DOCKER_PLATFORM         - Docker platform override"
    echo "  TRISHUL_DOCKER_PLATFORM - Alternate env name for Docker platform override"
    echo "  TRISHUL_SKIP_LEGACY_MIGRATION - Set to 1/true/yes/on to skip legacy volume migration"
    echo ""
    echo "Examples:"
    echo "  $0 up"
    echo "  $0 up --platform linux/arm64"
    echo "  $0 up-cached --image ghcr.io/${GHCR_USER}/trishul-snmp-suite:${PINNED_APP_VERSION}"
    echo "  APP_PORT=8980 SNMP_PORT=3161 TRAP_PORT=3162 $0 up"
    echo "  FRONTEND_PORT=8980 BACKEND_PORT=8900 $0 up-cached"
    echo "  FRONTEND_PORT=8980 BACKEND_PORT=8900 $0 up-cached --no-migrate"
    echo "  $0 backup"
}

require_commands() {
    command -v docker >/dev/null 2>&1 || fail "docker is not installed or not in PATH"
    command -v python3 >/dev/null 2>&1 || fail "python3 is not installed or not in PATH"
}

check_ghcr_login() {
    mapfile -t DOCKER_PLATFORM_ARGS < <(docker_platform_args)
    docker pull "${DOCKER_PLATFORM_ARGS[@]}" "$APP_IMAGE" >/dev/null 2>&1
}

login_ghcr() {
    echo -e "${BLUE}Checking GHCR access for ${APP_IMAGE}...${NC}"
    if check_ghcr_login; then
        echo -e "${GREEN}GHCR access OK${NC}"
        return 0
    fi
    echo -e "${YELLOW}Authentication may be required${NC}"
    if [ -n "$GHCR_TOKEN" ]; then
        echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
    else
        echo ""
        echo -e "${BLUE}Enter GitHub PAT (or press Enter to skip):${NC}"
        read -r -s -p "Token: " token
        echo ""
        if [ -n "$token" ]; then
            echo "$token" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
        else
            echo -e "${YELLOW}Skipping login...${NC}"
        fi
    fi
    if check_ghcr_login; then
        echo -e "${GREEN}GHCR login successful${NC}"
    else
        fail "Failed to access image ${APP_IMAGE}"
    fi
}

pull_images() {
    require_commands
    set_image_source "ghcr"
    if image_uses_ghcr; then
        login_ghcr
    fi

    mapfile -t DOCKER_PLATFORM_ARGS < <(docker_platform_args)
    echo "Pulling pinned image..."
    if [ -n "$DOCKER_PLATFORM" ]; then
        echo "   Platform:     $DOCKER_PLATFORM"
    fi
    echo "   Image:        $APP_IMAGE"
    docker pull "${DOCKER_PLATFORM_ARGS[@]}" "$APP_IMAGE"
    echo -e "${GREEN}Image pulled: ${APP_IMAGE}${NC}"
}

ensure_cached_image() {
    require_commands
    set_image_source "cached"
    if docker image inspect "$APP_IMAGE" >/dev/null 2>&1; then
        echo -e "${GREEN}Using cached image ${APP_IMAGE}${NC}"
        return 0
    fi
    fail "Cached image not found: ${APP_IMAGE}. Run '$0 pull' or 'docker pull ${APP_IMAGE}' first."
}

prepare_images() {
    if [ "$IMAGE_SOURCE" = "cached" ]; then
        ensure_cached_image
    else
        pull_images
    fi
}

volume_exists() {
    docker volume inspect "$1" >/dev/null 2>&1
}

volume_has_data() {
    local volume_name="$1"
    mapfile -t DOCKER_PLATFORM_ARGS < <(docker_platform_args)
    docker run --rm \
        "${DOCKER_PLATFORM_ARGS[@]}" \
        -v "${volume_name}:/data" \
        "$APP_IMAGE" \
        sh -c 'find /data -mindepth 1 -print -quit 2>/dev/null | grep -q .'
}

ensure_volume() {
    if ! volume_exists "$VOLUME_NAME"; then
        echo "Creating Docker volume: $VOLUME_NAME"
        docker volume create "$VOLUME_NAME" >/dev/null
        echo -e "${GREEN}Volume created${NC}"
    fi
}

migrate_legacy_volume() {
    if skip_legacy_migration_requested; then
        echo -e "${BLUE}Skipping legacy volume migration by request.${NC}"
        return 0
    fi

    if [ "$VOLUME_NAME" = "$LEGACY_VOLUME_NAME" ]; then
        return 0
    fi

    if ! volume_exists "$LEGACY_VOLUME_NAME"; then
        return 0
    fi

    ensure_volume

    if volume_has_data "$VOLUME_NAME"; then
        echo -e "${BLUE}Target volume already contains data; skipping legacy copy.${NC}"
        return 0
    fi

    mapfile -t DOCKER_PLATFORM_ARGS < <(docker_platform_args)
    echo -e "${BLUE}Migrating data from ${LEGACY_VOLUME_NAME} to ${VOLUME_NAME}...${NC}"
    docker run --rm \
        "${DOCKER_PLATFORM_ARGS[@]}" \
        -v "${LEGACY_VOLUME_NAME}:/from" \
        -v "${VOLUME_NAME}:/to" \
        "$APP_IMAGE" \
        sh -c 'cp -a /from/. /to/'
    echo -e "${GREEN}Legacy volume copied. Old volume preserved for rollback.${NC}"
}

cleanup_legacy_containers() {
    docker stop "$LEGACY_CONTAINER_BACKEND" "$LEGACY_CONTAINER_FRONTEND" 2>/dev/null || true
    docker rm "$LEGACY_CONTAINER_BACKEND" "$LEGACY_CONTAINER_FRONTEND" 2>/dev/null || true
}

cleanup_current_container() {
    docker stop "$CONTAINER_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_NAME" 2>/dev/null || true
}

port_args() {
    local args=(
        -p "${APP_PORT}:8000"
        -p "${SNMP_PORT}:${SNMP_PORT}/udp"
        -p "${TRAP_PORT}:${TRAP_PORT}/udp"
    )

    if [ -n "$BACKEND_COMPAT_PORT" ] && [ "$BACKEND_COMPAT_PORT" != "$APP_PORT" ]; then
        args+=(-p "${BACKEND_COMPAT_PORT}:8000")
    fi

    printf '%s\n' "${args[@]}"
}

legacy_runtime_env_args() {
    local allowed_origins="${ALLOWED_ORIGINS:-http://localhost:${APP_PORT},http://localhost:8000,http://localhost:8900,http://localhost:8980}"
    local args=(
        -e "APP_NAME=${RUNTIME_APP_NAME}"
        -e "APP_VERSION=${PINNED_APP_VERSION}"
        -e "APP_AUTHOR=${RUNTIME_APP_AUTHOR}"
        -e "APP_DESCRIPTION=${RUNTIME_APP_DESCRIPTION}"
        -e "SNMP_COMMUNITY=${RUNTIME_SNMP_COMMUNITY}"
        -e "SESSION_TIMEOUT=${RUNTIME_SESSION_TIMEOUT}"
        -e "AUTO_START_SIMULATOR=${RUNTIME_AUTO_START_SIMULATOR}"
        -e "AUTO_START_TRAP_RECEIVER=${RUNTIME_AUTO_START_TRAP_RECEIVER}"
        -e "MIB_AUTO_FETCH=${RUNTIME_MIB_AUTO_FETCH}"
        -e "WS_INTERNAL_PORT=${RUNTIME_WS_INTERNAL_PORT}"
        -e "ALLOWED_ORIGINS=${allowed_origins}"
    )

    printf '%s\n' "${args[@]}"
}

wait_for_app() {
    local port="$1"
    echo -n "Waiting for application on port ${port}"
    local i=0
    while [ $i -lt 30 ]; do
        if python3 -c "
import urllib.request, sys
try:
    urllib.request.urlopen('http://localhost:${port}/api/health', timeout=2)
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
            echo -e " ${GREEN}ready${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        i=$((i + 1))
    done
    echo -e " ${RED}timed out${NC}"
    return 1
}

print_access_info() {
    echo ""
    echo -e "${GREEN}Trishul SNMP Suite 1.4.1 is running.${NC}"
    echo ""
    echo "App URL:       http://localhost:${APP_PORT}"
    echo "API docs:      http://localhost:${APP_PORT}/docs"
    if [ -n "$BACKEND_COMPAT_PORT" ] && [ "$BACKEND_COMPAT_PORT" != "$APP_PORT" ]; then
        echo "Compat URL:    http://localhost:${BACKEND_COMPAT_PORT}"
    fi
    echo "SNMP UDP:      ${SNMP_PORT}"
    echo "Trap UDP:      ${TRAP_PORT}"
    echo "Container:     ${CONTAINER_NAME}"
    echo "Data volume:   ${VOLUME_NAME}"
    echo "Image:         ${APP_IMAGE}"
    if [ -n "$DOCKER_PLATFORM" ]; then
        echo "Platform:      ${DOCKER_PLATFORM}"
    fi
    echo ""
    echo "Default login: admin / admin123"
    echo -e "${YELLOW}Change the default password in Settings after first login.${NC}"
    echo ""
}

run_container() {
    require_commands
    prepare_images
    ensure_volume
    cleanup_legacy_containers
    cleanup_current_container
    migrate_legacy_volume

    mapfile -t PORT_ARGS < <(port_args)
    mapfile -t LEGACY_ENV_OVERRIDES < <(legacy_runtime_env_args)
    mapfile -t DOCKER_PLATFORM_ARGS < <(docker_platform_args)

    echo "Starting pinned 1.4.1 container..."
    echo "   Image source: $IMAGE_SOURCE"
    echo "   Image:        $APP_IMAGE"
    echo "   App port:     $APP_PORT"
    if [ -n "$BACKEND_COMPAT_PORT" ] && [ "$BACKEND_COMPAT_PORT" != "$APP_PORT" ]; then
        echo "   Compat port:  $BACKEND_COMPAT_PORT"
    fi
    echo "   SNMP port:    $SNMP_PORT/udp"
    echo "   Trap port:    $TRAP_PORT/udp"
    echo "   Container:    $CONTAINER_NAME"
    echo "   Data volume:  $VOLUME_NAME"
    if [ -n "$DOCKER_PLATFORM" ]; then
        echo "   Platform:     $DOCKER_PLATFORM"
    fi

    docker run -d \
        "${DOCKER_PLATFORM_ARGS[@]}" \
        --name "$CONTAINER_NAME" \
        "${ENV_ARGS[@]}" \
        "${LEGACY_ENV_OVERRIDES[@]}" \
        -v "${VOLUME_NAME}:/app/backend/data" \
        --restart unless-stopped \
        "${PORT_ARGS[@]}" \
        "$APP_IMAGE"

    wait_for_app "$APP_PORT"
    print_access_info
}

stop_container() {
    require_commands
    echo "Stopping Trishul SNMP Suite..."
    cleanup_current_container
    cleanup_legacy_containers
    echo -e "${GREEN}Containers stopped${NC}"
}

restart_container() {
    stop_container
    run_container
}

show_logs() {
    require_commands
    echo -e "${BLUE}Container logs (Ctrl+C to exit):${NC}"
    docker logs -f "$CONTAINER_NAME"
}

show_status() {
    require_commands
    echo "Container status:"
    docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" 2>/dev/null || true
    echo ""
    echo "Configuration:"
    echo "   Image source: $IMAGE_SOURCE"
    echo "   Image:        ${APP_IMAGE}"
    echo "   Container:    ${CONTAINER_NAME}"
    echo "   App port:     $APP_PORT"
    if [ -n "$BACKEND_COMPAT_PORT" ] && [ "$BACKEND_COMPAT_PORT" != "$APP_PORT" ]; then
        echo "   Compat port:  $BACKEND_COMPAT_PORT"
    fi
    echo "   SNMP port:    $SNMP_PORT/udp"
    echo "   Trap port:    $TRAP_PORT/udp"
    echo "   Data volume:  $VOLUME_NAME"
    echo "   Platform:     ${DOCKER_PLATFORM:-auto}"
    if volume_exists "$VOLUME_NAME"; then
        local mount_point
        mount_point=$(docker volume inspect "$VOLUME_NAME" --format '{{.Mountpoint}}')
        echo "   Volume path:  $mount_point"
    fi
    echo ""
    echo "Running image:"
    docker inspect "$CONTAINER_NAME" --format "   App: {{.Config.Image}}" 2>/dev/null || echo "   App: not running"
    local version
    version=$(python3 -c "
import urllib.request, json
try:
    response = urllib.request.urlopen('http://localhost:${APP_PORT}/api/meta', timeout=3)
    print(json.loads(response.read()).get('version', 'unknown'))
except Exception:
    print('unavailable')
" 2>/dev/null)
    echo "   App version: ${version}"
}

backup_data() {
    require_commands
    prepare_images
    mapfile -t DOCKER_PLATFORM_ARGS < <(docker_platform_args)
    local backup_file="trishul-snmp-backup-$(date +%Y%m%d-%H%M%S).tar.gz"
    echo "Creating backup: $backup_file"
    docker run --rm \
        "${DOCKER_PLATFORM_ARGS[@]}" \
        -v "${VOLUME_NAME}:/data" \
        -v "${PWD}:/backup" \
        "$APP_IMAGE" \
        tar czf "/backup/${backup_file}" -C /data .
    echo -e "${GREEN}Backup created: ${backup_file}${NC}"
}

restore_data() {
    require_commands
    local backup_file="$1"
    if [ -z "$backup_file" ]; then
        fail "backup file not specified. Usage: $0 restore <backup-file.tar.gz>"
    fi
    if [ ! -f "$backup_file" ]; then
        fail "backup file not found: ${backup_file}"
    fi

    prepare_images
    mapfile -t DOCKER_PLATFORM_ARGS < <(docker_platform_args)
    stop_container
    ensure_volume
    echo "Restoring from: $backup_file"
    docker run --rm \
        "${DOCKER_PLATFORM_ARGS[@]}" \
        -v "${VOLUME_NAME}:/data" \
        -v "${PWD}:/backup" \
        "$APP_IMAGE" \
        sh -c "rm -rf /data/* && tar xzf /backup/${backup_file} -C /data"
    echo -e "${GREEN}Data restored${NC}"
    echo -e "${BLUE}Run '$0 up' or '$0 up-cached' to restart.${NC}"
}

if [ $# -gt 0 ]; then
    COMMAND="$1"
    shift
fi

parse_cli_args "$@"
DOCKER_PLATFORM="$(normalize_platform "$DOCKER_PLATFORM")"
validate_command_args
set_image_source "$IMAGE_SOURCE"

case "$COMMAND" in
    up)              run_container ;;
    up-cached)       set_image_source "cached"; run_container ;;
    down)            stop_container ;;
    restart)         restart_container ;;
    restart-cached)  set_image_source "cached"; restart_container ;;
    pull)            pull_images ;;
    logs|logs-frontend) show_logs ;;
    status)          show_status ;;
    backup)          backup_data ;;
    restore)         restore_data "$RESTORE_FILE" ;;
    help|-h|--help)  show_usage ;;
    *)
        show_usage
        exit 1
        ;;
esac
