We're going to talk about why Cub exists and what it is useful for.

A lot of people are building AI-driven coding agents that can do larger and larger chunks of work autonomously. They work best when they have a clear set of instructions itemized as tasks.

With the latest models like Opus 4.5, these systems can operate for hours on end and produce code that is passable, if not perfect, in one shot. It can then also identify bugs, run tests, fix up the code to get it somewhere near production quality.

Different people's mileage varies based on the type of thing they're trying to build, their willingness to operate in a different way, and phases of the moon.

In general, it feels like we are moving toward a model of evolving and improving capabilities rapidly in 2026. This means that technical people can ship more software, and less technical people can ship some amount of software.

The purpose of Cub is to build a tool that takes advantage of and leans into this moment while trying to also provide a set of features to make life easier.

So, for starters, in no particular order, one of the main goals is to support multiple command-line interface harnesses (so things like Claude Code, Opening AIs Codex, and OpenCode) because they have somewhat different strengths, and any project of suitable size can benefit from the relative strengths of the different harnesses.

Partly because they're all evolving so rapidly that new capabilities emerge in one that may not be available in the others, partly to avoid vendor lock-in, and partly to manage tokens as resources that can be applied.

Closely coupled with that is the idea of being able to identify the appropriate level of sophistication of a model for a task instead of running everything (both complex tasks and simple ones) through an incredibly high-end model like Opus.

This makes it possible to automatically run simple renaming tasks and refactoring tasks and things like that with something like Haiku, medium-sized tasks with medium complexity tasks with Sonnet, and then reserve Opus for the most complex tasks and planning.

Cub also provides distinct prep and run workflows; the idea being that it helps to go through a process of scooping up any vision documents, specs, other inputs, and go through a structured interview process to ultimately produce well-defined tasks that an agent can pick up.

Cub supports a few different backends for storing and managing these tasks. It works closely with Steve Yuggie's BEEDS system, which is also under active and evolving development, and it can also work with a simple JSON file as a backend.

The goal here is keeping the functionality that preps these tasks close together but somewhat distinct so that there's a moment in time opportunity for the operator of this system to come in and make adjustments in review before code tasks are kicked off. 


 using the BEEDS format, individual tasks are itemized with clear acceptance criteria and a set of specific instructions. Tasks are generally grouped into epics that describe a feature in total. It feels like we're at a stage of progress with models and patterns of usage of these models where we can somewhat reliably expect a well-structured epic to be implemented autonomously, and that the system can produce a pull request against an existing codebase and either review, close, merge, and release it itself, or wait for human input. When creating tasks in epics, doing the proper labeling so that they can be filtered and executed well is important. Another feature as we all get more acquainted with how these things run is logging what harnesses are doing when left on their own so that we can understand what's working well and what isn't, and use those logs as input to improve both the application-level execution of successive tasks to avoid pitfalls over and over again (looking for files in the wrong place, etc.) as well as improving Cub overall. The core loop and one of the reasons for doing this outside of any individual harness is to make the core loop of deciding on a task, figuring out how to execute that task (which harness to use, which model, etc.), setting up that job, deciding whether there's success or failure, figuring out if it's worth retrying or continuing on. It creates its own importance in building that logic at a layer that works deterministically since that is effectively a state machine, and it makes more sense to use traditional software than LLMs to run state machines. It also creates the opportunity for deterministically executed hooks and plugins so that when you have something that you want to happen (for instance, an email notification when a task or loop is complete), that can happen reliably without having to hope that an LLM re-read the agent file at the right time. There's also an interest in pulling this together in building out other subcommands that help with this type of project. For instance, adding an audit that looks for dead code and other artifacts of how LLMs produce software to try to keep the repository and codebase relatively tight and clean. Another is asking it to reflect and create additional guard rails based on its runs so that we can find out what it could be doing better, and that it can operate with some kind of memory-driven self-improvement in each successive loop. These are things that are beneficial to operate outside of any individual harness or any individual session inside of a CLI 


The other big thing to cover is the prep steps. Right now, this drops you into a Claude Code session with four stages wired up. The idea is that you bring any ideas or documents you have (whether it's a single sentence or a whole set of specs) and go through an interview process to turn that into tasks that are written out for CUB to then run against.
	1	Triage step - just trying to get a handle on what's trying to be accomplished and what the goals are (things like that).
	2	Architecture step - diving deeper specifically into what makes sense from a technical implementation perspective and making sure that there's a clear plan for how this body of work ultimately manifests.
	3	Planning step - takes the inputs from the first two and chunks things up into pieces and sequencing that make sense for an LLM to be able to accomplish and works to ensure that there's the appropriate context at the task level for the LLM to be able to work effectively.
	4	Bootstrapping process - migrates the outputs of this prep into the appropriate task backend that CUB is using for that project (whether that's a JSON file or BEEDS).
The goal of this interview process is to make sure that we're looking at the opportunities the right way and getting structured output that is fleshed out enough for the system to work in a way that is observable before any of the work is taken on. The goal of this part of the system is to be smart about understanding decisions that have already been made, precedent that's already been set (whether that's in the existing codebase or in the docs that are provided as part of the set of new features), but then also not let gaps in specificity or understanding slip through.
