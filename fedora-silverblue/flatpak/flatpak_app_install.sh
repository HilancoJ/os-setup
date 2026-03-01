#!/usr/bin/env bash
# ===================================================================================================
# flatpak_app_install.sh - Install Flatpak applications from an App List
# ===================================================================================================

# Capture exit codes in pipes
set -uo pipefail

# ===================================================================================================
# Configuration
# ===================================================================================================
APP_LIST_FILE="$1"

# ===================================================================================================
# Validation
# ===================================================================================================
if [ ! -f "$APP_LIST_FILE" ]; then
    echo "ERROR: Flatpak App List was not provided or the File cannot be found."
    exit 1
fi

# ===================================================================================================
# Parse App List
# ===================================================================================================
declare -a app_names
declare -a app_ids
max_name_len=0
max_id_len=0

# Read and process the app list file
while IFS='|' read -r name id; do

    # Store app name and ID in arrays
    app_names+=("$name")
    app_ids+=("$id")

    # Calculate max lengths while reading
    name_len=${#name}
    id_len=${#id}
    [ $name_len -gt $max_name_len ] && max_name_len=$name_len
    [ $id_len -gt $max_id_len ] && max_id_len=$id_len

done < <(awk -F ':' '/:/ {
    # Remove leading hyphens, whitespace, and tabs from app name
    gsub(/^[ \t-]+/, "", $1)

    # Remove markdown bold formatting (**) from app name
    gsub(/\*\*/, "", $1)

    # Remove leading whitespace from Flatpak ID
    gsub(/^[ \t]+/, "", $2)

    # Output in pipe-delimited format: name|id
    print $1 "|" $2
}' "$APP_LIST_FILE")

# Add padding to column widths
PADDING=4
NAME_WIDTH=$((max_name_len + PADDING))
ID_WIDTH=$((max_id_len + PADDING))
STATUS_WIDTH=30
TOTAL_WIDTH=$((NAME_WIDTH + ID_WIDTH + STATUS_WIDTH))

# Generate separator lines
TOP_SEP=$(printf '=%.0s' $(seq 1 $TOTAL_WIDTH))
MID_SEP=$(printf -- '-%.0s' $(seq 1 $TOTAL_WIDTH))

# ===================================================================================================
# Display Header
# ===================================================================================================
echo "$TOP_SEP"
echo "Installing Flatpak applications from: '$APP_LIST_FILE'"
echo "$TOP_SEP"
printf "%-${NAME_WIDTH}s %-${ID_WIDTH}s %s\n" "Application" "Flatpak ID" "Status"
echo "$MID_SEP"

# ===================================================================================================
# Install Applications
# ===================================================================================================
for i in "${!app_names[@]}"; do
    name="${app_names[$i]}"
    id="${app_ids[$i]}"

    # Display app name and ID with dynamic column widths
    printf "%-${NAME_WIDTH}s %-${ID_WIDTH}s " "$name" "$id"

    # Create temporary file to capture full output for status checking
    temp_output=$(mktemp)

    # Install the application with live progress display
    # - stdbuf -oL: Disable output buffering for real-time streaming
    # - tee: Capture output to temp file while passing it to the pipeline
    # - Inner while loop: Filter and display only progress lines
    stdbuf -oL flatpak install -y flathub "$id" 2>&1 | tee "$temp_output" | \
    while IFS= read -r line; do
        # Check if line contains installation progress (e.g., "Installing... 73%")
        if echo "$line" | grep -q "Installing.*[0-9].*%"; then
            # Overwrite current line with app info and progress status
            printf "\r%-${NAME_WIDTH}s %-${ID_WIDTH}s %s" "$name" "$id" "$line"
        fi
    done

    # Capture exit code from flatpak command (before pipes)
    exit_code=${PIPESTATUS[0]}

    # Read full output from temp file for status determination
    output=$(cat "$temp_output")
    rm -f "$temp_output"

    # Clear the entire line using ANSI escape code, then reprint app info for final status
    printf "\r\033[K%-${NAME_WIDTH}s %-${ID_WIDTH}s " "$name" "$id"

    # Determine and display final installation status
    if echo "$output" | grep -q "is already installed"; then
        # App was already installed (possibly from different remote)
        echo "Already Installed"
    elif [ $exit_code -eq 0 ]; then
        # Installation succeeded
        echo "Installed Successfully"
    else
        # Installation failed
        echo "Installation Failed"
    fi
done

# ===================================================================================================
# Display Footer
# ===================================================================================================
echo "$TOP_SEP"
echo "Installation complete!"
echo "$TOP_SEP"
