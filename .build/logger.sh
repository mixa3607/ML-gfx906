#!/usr/bin/env bash
# https://gist.github.com/peter-bloomfield/fa3c2da60cb1ec5d1630ac83ae01917d

# Function echo text to the screen.
# There are two ways to invoke this:
#
#  print LEVEL MESSAGE
#  print MESSAGE
#
# In the first case, LEVEL can be one of: DEBUG, INFO, SUCCESS, WARNING, or ERROR.
# This determines the colour used to display the message. If the level is not recognised then it defaults to INFO.
# In the second case, the message is displayed as though LEVEL was set to INFO.
function print
{
    # If there are two arguments then the first is LEVEL and the second is MESSAGE.
    # If there is only one argument then it is the message. LEVEL defaults to INFO.
    local level="${1:-}"
    local message="${2:-}"
    if [[ "${message}" = "" ]]; then
        message="${1:-}"
        level="INFO"
    fi

    local format="\e[0m"
    local resetFormat="\e[0m"
    local paddedLevel="$(printf "%-4s" "${level}")"
    local prefix="[${paddedLevel}] "

    # Pick a suitable display colour.
    case "${level}" in
        "DBG" )
            # Dim text
            format="\e[2m"
            ;;
        "INFO" )
            # Default text format.
            ;;
        "WARN" )
            # Yellow text.
            format="\e[33m"
            ;;
        "ERR" )
            # Bold/bright red text.
            format="\e[1;31m"
            ;;
        * )
            # Use default format.
            ;;
    esac

    echo -e "${resetFormat}${format}${prefix}${message}${resetFormat}"
}
