Feature: Fixed URL single-page extraction quality
  Validate the existing workbench without adding a crawler.

  Scenario: Navigation waits even on a normal HTTP 200 page
    Given a normal browser page and a configured navigation delay
    When the browser-backed collector reads the URL
    Then it waits the full delay once and retains the final document response

  Scenario: Optional missing fields do not fail verification
    Given a valid required title and an empty optional description
    When I verify the extraction
    Then verification passes without penalizing the absent optional field

  Scenario: Required numeric zero is a value
    Given a required numeric field with the value zero and supporting evidence
    When I verify the extraction
    Then verification does not report a required field missing

  Scenario: Nested DOM selectors preserve only the selected content
    Given nested resource markup with images and a sidebar
    When I execute a scoped CSS and XPath program
    Then the body excludes the sidebar and XPath selects the version

  Scenario: Overbroad generated rules are rejected
    Given generated document title and ambiguous body selectors
    When I validate those generated rules against the current page
    Then those rules are rejected with diagnostics

  Scenario: Optional completeness cannot be hidden by a verifier score gain
    Given comparable runs with a higher score but fewer extracted fields
    When I evaluate their RSI iteration
    Then the iteration is rejected for a completeness regression

  Scenario: Evaluator versions cannot be mixed
    Given otherwise comparable runs with different evaluator versions
    When I evaluate their RSI iteration
    Then the iteration is blocked for evaluator incompatibility

  Scenario: Missing guardrail measurements cannot be accepted
    Given comparable runs with a missing evidence coverage measurement
    When I evaluate their RSI iteration
    Then the iteration is blocked for unavailable guardrail measurements

  Scenario: Better completion can improve quality without changing verifier score
    Given comparable runs with equal verifier scores and better candidate completion
    When I evaluate their RSI iteration
    Then the iteration is accepted using a completion-aware quality proxy

  Scenario: Qualified document-level selectors cannot evade validation
    Given generated qualified root and document title selectors
    When I validate those generated rules against the current page
    Then those rules are rejected as document scope
