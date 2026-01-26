Some notes for the things I want to be true for us to label and tag a release as a first public alpha. The threshold is that someone who's reasonably conversant with CLI coding tools can get Cub up and running and quickly understand how to graft it into their existing workflow and get value. Other docs lay out the more strategic aspects of the value prop for public alpha 1 and beyond, this is more about brass tacks work that needs to be done and/or validated.

## Project positioning

* probably for soloists for now. need clear disclaimers in docs, readme etc that this dangerously skips permissions and should be run in an environment where that's not an issue.

## Smooth installation process

* we have an install.sh script that is reasonably resilient. we should test it in more scenarios (missing dependencies, etc), and ensure there's clear fallback messaging for manual install, re-install, and bug filing.

## Logical onboarding process for cub at a system level and project level

* we have cub init. 
* we could make it easy to launch docs in the browser from the command line. `cub docs`

## Clear steps for new repos and existing codebases

* a cub analyze command could get a handle on an existing codebase.
* cub new could create a new project with the right scaffolding, and could operate with a file (vision, prd, etc) to figure out what to do. it could drop into interview mode or, with --auto, just make best guesses.

## Solid relationship with harness-driven work

* using claude/codex directly vs cub should not feel like an either/or proposition. if you're in the harness, we should still log, ideally sync with tasks in the background, etc.

## Ensure non-beads task management works properly

* potentially flip the default for now since small/medium projects don't need the overhead and complexity. it can be something that projects migrate into.
* could potentially factor out a standalone lib in python that implements a subset of the beads features in a way that's more reliable for our needs.

## Up-to-date and useful docs

* need to make sure these reflect the codebase and we have a good process for keeping these in sync over time.

## Clearly mark untested/experimental aspects

* for instance, we haven't really used the sandbox functionality at all. we can hide/shroud it for now.
