# DVM-ABM v25.7 field-interaction demand multiplier patch

This patch updates only:

```text
dvm_abm/model.py
```

It adds a sensitivity-only parameter:

```text
field_interaction_demand_multiplier
```

Default value:

```text
1.0
```

The default preserves v25.6 behaviour. The parameter is used by the v8 sensitivity harness in the threshold test:

```text
supervisor_capacity × field_interaction_demand_multiplier
```

The multiplier changes routine field-interaction demand per active crew. Higher values create a more demanding workface interaction environment and make it possible to test when supervisor field-support capacity becomes a bottleneck.

You do not need to edit `scenarios.py` or `scenarios.yaml`; the v8 harness attaches this as a virtual Scenario attribute during threshold runs.
