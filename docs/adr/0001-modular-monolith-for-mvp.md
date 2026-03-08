# ADR 0001: Modular Monolith for MVP

## Status

Accepted

## Context

The PRD calls for multiple logical services, but the repository contains no code yet and the environment currently lacks a local language runtime.

## Decision

Implement the MVP as one FastAPI service with explicit internal module boundaries for vision, retrieval, agent workflow, notification, and dashboard rendering.

## Consequences

- Faster delivery of the complete PRD path
- Easier Docker-based local setup
- Clean seams remain for later service extraction