"""Domain layer: the pure, I/O-free core of Momentum25.

Contains entities, value objects, ports (interfaces), and the engine/rule/strategy
contracts. Per ADR-001 and ADR-009, nothing here performs I/O or depends on outer
layers, and all behaviour is deterministic.
"""
