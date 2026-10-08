Feature: RSI evidence and iteration evaluation
  Observation prepares supervised improvement; it does not modify code or deploy rules.

  Scenario: A rendered page is handled without challenge markup recognition
    Given a rendered HTTP 200 page with challenge-like markup
    When I submit that URL for extraction
    Then the collection attempt is classified from generic content and status
    And the page is not rejected by challenge markup
    And the failed run retains structured collection observations

  Scenario: A transient challenge finishes through normal browser navigation
    Given a CloakBrowser page initially returning 468 that automatically navigates to 200
    When the browser-backed collector reads the URL
    Then the final document status and content are collected without HTTP fallback
    And the initial status and bounded wait observations remain available

  Scenario: A persistent access-limited page stops at the configured wait deadline
    Given a CloakBrowser page that remains access-limited after the configured wait deadline
    When the browser-backed collector reads the URL
    Then collection fails without HTTP fallback or page-specific recognition
    And wait timeout observations and browser cleanup are retained

  Scenario: Comparable baseline and candidate can be evaluated and retrieved
    Given completed baseline and candidate runs of the same page and schema
    When I evaluate an RSI iteration with a hypothesis and change identifier
    Then the stored iteration links both runs and reports metric deltas
    And the decision is accepted when quality improves without excessive latency regression
    And evaluation does not alter either extraction run

  Scenario: Incomparable runs cannot claim improvement
    Given baseline and candidate runs with different page snapshots
    When I evaluate an RSI iteration with a hypothesis and change identifier
    Then the iteration is blocked with a comparability reason

  Scenario: Actual token usage is never fabricated
    Given a model response without provider token usage
    When the model call is observed
    Then actual token usage is unavailable and estimates are labelled estimated

  Scenario: Zero model calls have zero token cost
    Given a program-only benchmark record with no model calls
    When I score that benchmark record
    Then token cost is measured zero and repair success is unavailable
    And selective accuracy uses field confidence and missing rate uses required fields

  Scenario: Summary includes empirical latency and zero-denominator reasons
    Given an empty monitoring window
    When I query the monitoring summary
    Then latency percentiles and failure rate are unavailable rather than fabricated zero

  Scenario: Direct LLM measures a single schema-free record call
    Given a model provider returning a generic record with measured usage
    When I run the Direct LLM benchmark method
    Then exactly one model HTTP call is recorded with provider usage
    And neither the target schema nor gold answers appear in its prompt

  Scenario: Failed model HTTP attempts are still counted
    Given a model provider whose HTTP request fails
    When I run the Direct LLM benchmark method
    Then the failed sample retains one attempted call and unavailable usage

  Scenario: Program methods share a cold-start program and repair is scored against gold
    Given a labelled sample with one incorrect field before repair
    When I run the full benchmark method with a controlled repair result
    Then repair success counts only wrong-to-right gold improvements
    And the full method receives the shared deterministic program without history reuse

  Scenario: Accepted iterations can be rolled back with a reason
    Given completed baseline and candidate runs of the same page and schema
    When I evaluate an RSI iteration with a hypothesis and change identifier
    And I record a human rollback reason
    Then rollback is idempotent and original run metrics are unchanged
