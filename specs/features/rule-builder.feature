Feature: Snapshot rule builder
  Field selection and field extraction are separate AI collaboration workflows.

  Scenario: Schema collaboration changes only the field proposal
    Given a saved builder page snapshot
    When I ask the schema agent to split the resource name into two fields
    Then it returns a schema proposal without values or programs
    And the page collector is not called

  Scenario: Value collaboration updates exactly one field
    Given a saved builder page snapshot
    When I guide the plugin name field to the title text
    Then the value agent returns one field value and its executable rules
    And its evidence refers to the saved snapshot
    And the page collector is not called

  Scenario: Unsupported evidence cannot become an extracted fact
    Given a saved builder page snapshot
    When the value agent invents evidence absent from the snapshot
    Then value collaboration rejects the unsupported fact

  Scenario: Quality check executes the revised rule before saving
    Given a saved builder page snapshot
    When I check the active fields and revised rules
    Then the check returns a freshly verified persisted extraction
    And the page collector is not called

  Scenario: Guidance mismatch prevents verified publication
    Given a saved builder page snapshot
    When I check rules that do not reproduce the guided value
    Then the quality check fails with a guidance mismatch

  Scenario: Verified save must match the checked candidate
    Given a saved builder page snapshot
    When I try to publish an unchecked builder candidate
    Then verified publication is rejected

  Scenario: Collaboration requires an existing snapshot
    When I request field collaboration for an unknown task
    Then the builder returns a not found error
