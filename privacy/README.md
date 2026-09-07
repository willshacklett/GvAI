# GVAI Private Build Mode

Private Build Mode is a universal GVAI capability.

It is not specific to GVAI's creators.

Every GVAI user can create private projects protected by the same policy.

## Fundamental rule

WORLD -> GVAI = ALLOWED

PRIVATE GVAI DATA -> WORLD = DENIED BY DEFAULT

## Private Build Mode

When enabled:

- GVAI can retrieve public web information.
- GVAI can retrieve research and public datasets.
- GVAI can receive market/economic information.
- Local GVAI models and tools can process project information.
- Private project information cannot be sent to an external AI.
- Private project information cannot be written to an outside service.
- Users can explicitly authorize selected information to leave.

## Architecture

Every external provider must eventually pass through:

PrivacyRouter
    |
    +-- local ------------ ALLOW
    |
    +-- world_read ------- ALLOW
    |
    +-- external_model --- POLICY CHECK
    |
    +-- external_write --- POLICY CHECK

The router is below the interface layer.

No future GVAI interface, agent, plugin, or AI provider should be able
to bypass the privacy gate.

## Philosophy

GVAI should have access to humanity's public knowledge without requiring
people to surrender ownership of their private ideas.
