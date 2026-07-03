# Decisions Log

## D-0001
Git is the single source of truth.

## D-0002
English is the canonical project language.
Russian is a synchronized translation.

## D-0003
Engineering over Perfection.

## D-0004
The project consists of a White Paper, Architecture Specification and Reference Implementation.

## D-0005
Kernel must remain independent of any specific LLM.

## D-0006
Project memory is layered.

## D-0007
Every document must be reachable from repository navigation.

## D-0008
Every Patch must leave the repository in a consistent, navigable state.

## D-0009
Repository content overrides chat history.

## D-0010
BOOT.md defines the canonical repository loading sequence.

## D-0011
SYSTEM_PROMPT.md defines permanent behavioural rules.

## D-0012
Every commit must improve the repository as a complete knowledge system.

## D-0013
Recurring engineering practices must be documented as repository protocols.

## D-0014
No important project knowledge may remain only inside chat history.

## D-0015
The repository stores both project knowledge and engineering processes.

## D-0016
A commit should represent exactly one conceptual change.

## D-0017
Validate Before Elaborating.
Implement new architectural layers only after validating the previous ones.

## D-0018
Infrastructure Before Features.
Improve development infrastructure before relying on new capabilities.


## D-0019
Patch Format v2 is the standard modification format. Large documents should be modified incrementally instead of being fully overwritten.

## D-0020
Human assistance is a fallback mechanism. Every automatic repository access method must be attempted before requesting manual intervention.

## D-0021
The repository should be executable engineering memory. A new session should recover project state from the repository rather than chat history.


## D-0022
The success criterion for repository memory is a Zero Context Recovery Test. A new LLM session must be able to resume the project using only the repository.

## D-0023
Every repository boot must produce a standardized Boot Report. Boot success is determined by loading repository state rather than by subjective interpretation.

## D-0024
Phase 0 is complete only after a successful Zero Context Recovery Test and correction of all deficiencies discovered during that test.

## D-0025
The repository must always define exactly one current engineering task. LLMs should execute that task instead of inferring the next objective.