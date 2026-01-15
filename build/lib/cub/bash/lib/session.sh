#!/usr/bin/env bash
#
# session.sh - Session identity and management
#
# Provides functions for generating session identities with friendly,
# memorable animal names for distinguishing concurrent cub instances.
#
# Functions:
#   session_random_name() - Returns a random animal name
#   session_init() - Initialize session with optional --name parameter
#   session_get_name() - Get the session name
#   session_get_id() - Get the session ID
#   session_get_run_id() - Get the run ID (alias for session_get_id)
#   session_is_initialized() - Check if session has been initialized
#

# Array of ~100 animal names (lowercase, single words)
ANIMAL_NAMES="aardvark albatross alpaca alligator anaconda ant anteater antelope ape armadillo badger bat bear beaver bee bison boar bobcat buffalo butterfly camel caribou cat caterpillar cheetah chimpanzee chinchilla chipmunk cobra cockroach cougar coyote crab crane crocodile crow cucumber cuckoo deer dingo dinosaur dog dolphin donkey dove dragonfly duck duffalo eagle eel eland elephant elk emu falcon ferret finch fish flamingo fly fox frog giraffe gnu goat goldfish goose gorilla grasshopper grouse guinea hare hawk hedgehog heron hippopotamus hornet horse hound hyena ibis icebear iguana impala insect jackal jaguar jay jellyfish jobfish kangaroo koala krill ladybug leopard lion llama locust loon lynx macaw magpie manatee mandrill meerkat mink minnow mole mongoose monkey moose mosquito moth mouse mule narwhal newt nightingale ocelot octopus otter owl ox panda panther parrot peccary pelican penguin pheasant pig pigeon pika pike poodle porcupine prairie puffin quail quokka rabbit raccoon raven reindeer rhinoceros rooster salmon saltpans sandpiper sardine seahorse seal sealion seaotter shark shearwater sheep shellduck shrew shrimp skunk sloth snail snake snipe snowgoose squirrel starfish stingray stork sturgeon swallow swan swift tapir tern tiger toad toucan turkey turtle uakari unau urchin urus viper vole vulture wallaby walrus wasp weasel weaver whale wolf wolverine wombat woodcock woodpecker wren"

# Global variables for session state
_SESSION_NAME=""
_SESSION_ID=""
_SESSION_STARTED_AT=""

# Pick a random animal name from the animal names
# Returns: a random animal name
session_random_name() {
    local animals
    local count
    local index

    # Convert the space-separated string into an array-like structure for selection
    animals=($ANIMAL_NAMES)
    count=${#animals[@]}

    # Use $RANDOM to get a random index
    index=$((RANDOM % count))

    echo "${animals[$index]}"
}

# Initialize a session with optional name override
# Usage: session_init [--name NAME]
# If --name is provided, uses that name. Otherwise generates a random animal name.
# Generates session ID as {name}-{YYYYMMDD-HHMMSS}
# Stores started_at in ISO 8601 format
session_init() {
    local session_name=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --name)
                session_name="$2"
                shift 2
                ;;
            *)
                echo "ERROR: Unknown option: $1" >&2
                return 1
                ;;
        esac
    done

    # Use provided name or generate random animal name
    if [[ -z "$session_name" ]]; then
        session_name=$(session_random_name)
    fi

    # Generate session ID with timestamp
    local timestamp
    timestamp=$(date +%Y%m%d-%H%M%S)

    # Store session state in global variables
    _SESSION_NAME="$session_name"
    _SESSION_ID="${session_name}-${timestamp}"
    _SESSION_STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    return 0
}

# Get the session name
# Returns: session name or error if not initialized
session_get_name() {
    if [[ -z "$_SESSION_NAME" ]]; then
        echo "ERROR: Session not initialized. Call session_init first." >&2
        return 1
    fi
    echo "$_SESSION_NAME"
}

# Get the session ID
# Returns: session ID in format {name}-{YYYYMMDD-HHMMSS}
session_get_id() {
    if [[ -z "$_SESSION_ID" ]]; then
        echo "ERROR: Session not initialized. Call session_init first." >&2
        return 1
    fi
    echo "$_SESSION_ID"
}

# Get the run ID (alias for session_get_id)
# Returns: session ID
session_get_run_id() {
    session_get_id
}

# Check if session has been initialized
# Returns: 0 if initialized, 1 if not
session_is_initialized() {
    if [[ -n "$_SESSION_ID" ]]; then
        return 0
    fi
    return 1
}
