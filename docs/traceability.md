# From the policy to the code

One row for each rule the policy states: where the code implements it and which tests exercise
it. The rules are described in our own words, because the policy file is participant-only data.
Code is under `system/screening/` and tests are under `system/tests/`.

Every function and test named here was found by a search of the repo when this file was
written. `COVERED` means there is code and at least one test, `CODE ONLY` that no test was
found, and `MISSING` that no code was found.

## The nine principles

Principle 6 is split into its five grounds for clearing, and principle 8 into its clauses.

| # | Rule, in our words | Code | Tests | Status |
|---|---|---|---|---|
| 1 | Decide identity only; how serious the listing is never changes the answer. | `decide.py`: `decide` | `test_pipeline.py`: `test_30_the_kind_of_listing_does_not_change_the_answer` | COVERED |
| 2 | Find the customer by the alert's link, or by searching the records. | `resolve.py`: `candidates`, `search`, `fits` | `test_pipeline.py`: `test_01_account_link_and_verified_date_of_birth`, `test_02_joint_account_screened_details_pick_the_holder`, `test_05_no_link_search_then_location`, `test_08_no_record_fits`, `test_24_a_link_that_leads_nowhere_falls_back_to_the_search` | COVERED |
| 3 | Merge records that are one person; several different people make it ambiguous. | `resolve.py`: `person_of`, `people`; `decide.py`: `combine` | `test_pipeline.py`: `test_09_same_phone_and_date_of_birth_is_one_person`, `test_10_same_phone_alone_is_family`, `test_23_same_document_number_is_one_person`, `test_06_two_people_fit_and_disagree`, `test_07_two_people_fit_and_agree` | COVERED |
| 4 | The latest approved identity check outranks declared details, as a row or a note. | `resolve.py`: `picture`, `is_approved`, `believable`; `extract.py`: `read_identity_note` | `test_pipeline.py`: `test_03_verified_name_beats_the_record_name`, `test_11_rejected_check_is_not_evidence`, `test_12_approved_check_written_only_as_a_note`, `test_26_a_failed_check_in_a_note_is_not_evidence`; `test_wording.py`: `test_a_later_support_note_does_not_hide_a_verified_name` | COVERED |
| 5 | Take the hit's birth date from its field, then its notes, then search results. | `watchlist.py`: `build_hit`; `extract.py`: `profile_birth`, `search_birth`, `result_about_hit` | `test_extract.py`: `test_birth_sentences`, `test_only_results_about_the_hit_count`; `test_pipeline.py`: `test_20_search_result_about_the_hit_not_a_namesake` | COVERED |
| 6a | Clear on time: too young at the first report, or the listed person died first. | `decide.py`: `decide`; `dates.py`: `surely_before`; `extract.py`: `dated_reports` | `test_pipeline.py`: `test_21_too_young_at_the_earliest_report`, `test_14_company_incorporated_after_the_report`, `test_16_died_before_screening`, `test_17_died_after_screening_does_not_clear`; `test_extract.py`: `test_only_the_exact_form_counts` | COVERED |
| 6b | Clear on date of birth only when every date the hit gives is contradicted. | `dates.py`: `contradicts`, `compare`; `decide.py`: `decide` | `test_rules.py`: `test_compare`, `test_dob_mismatch_evidence`; `test_ambiguous_dates.py`: `test_contradicted_only_when_both_readings_are` | COVERED |
| 6c | Clear on country when none is shared, unless name and birth date agree. | `decide.py`: `location_state`, `_location`, `short_name_agrees`; `countries.py`: `resolve`; `extract.py`: `lived_in` | `test_rules.py`: `test_location_mismatch`, `test_unreadable_country_blocks_location_clearance`; `test_pipeline.py`: `test_18_country_difference_does_not_clear_name_and_date`, `test_22_a_note_about_where_they_lived_blocks_a_location_clearance`, `test_28_a_one_part_name_that_agrees_stops_a_country_clearance` | COVERED |
| 6d | Clear on name only when the verified legal name matches none of the hit's. | `decide.py`: `name_state` | `test_rules.py`: `test_verified_name_beats_record_name`, `test_unverified_name_never_clears`; `test_wording.py`: `test_a_name_the_bank_does_not_hold_supports_but_never_clears` | COVERED |
| 6e | Clear when one side is a person and the other a company. | `decide.py`: `decide`; `resolve.py`: `kind_of` | `test_rules.py`: `test_entity_type`; `test_pipeline.py`: `test_15_person_against_company` | COVERED |
| 7 | Confirm a person on name and birth date, a company on name and country. | `decide.py`: `decide`; `dates.py`: `agrees` | `test_pipeline.py`: `test_04_email_link_name_and_date_agree`, `test_13_company_name_and_country`; `test_rules.py`: `test_company` | COVERED |
| 8a | Names ignore case, accents, punctuation and anything in brackets. | `names.py`: `parts`, `strip_brackets`; `textutil.py`: `fold` | `test_rules.py`: `test_parts` | COVERED |
| 8b | Single letters are initials, not parts; a repeated part counts once. | `names.py`: `parts` | `test_rules.py`: `test_parts` | COVERED |
| 8c | Spellings grouped in the variants file are the same part. | `names.py`: `part_match`, `from_file` | `test_rules.py`: `test_part_match`, `test_variants_file` | COVERED |
| 8d | A part written together or apart is one part. | `names.py`: `_best` | `test_rules.py`: `test_agree` | COVERED |
| 8e | One edit allowed for 4 to 6 letters, two for longer, none for shorter. | `names.py`: `_within`, `part_match` | `test_rules.py`: `test_part_match` | COVERED |
| 8f | Names agree on two matching parts, or on every part of the shorter. | `names.py`: `agree` | `test_rules.py`: `test_agree` | COVERED |
| 8g | Placeholders are not parts; a one-part personal name neither confirms nor clears. | `names.py`: `_is_placeholder`; `decide.py`: `name_state`, `short_name_agrees` | `test_rules.py`: `test_placeholders_are_not_parts`, `test_too_few_name_parts`; `test_pipeline.py`: `test_19_one_real_name_part_neither_clears_nor_confirms`, `test_29_a_one_part_name_still_clears_on_country_without_that_agreement` | COVERED |
| 8h | A company's legal form is not a name part. | `names.py`: `parts` | `test_rules.py`: `test_company_legal_forms`, `test_company_agree` | COVERED |
| 9 | Cite the records that decided the hit, and name the customer record. | `decide.py`: `decide`; `pipeline.py`: `process`, `_found_sentence` | `test_rules.py`: `test_dob_mismatch_evidence`; `test_pipeline.py`: `test_12_approved_check_written_only_as_a_note`, `test_16_died_before_screening` | COVERED |

## The eleven reason codes

| Code | What it means | Code | Tests | Status |
|---|---|---|---|---|
| `DOB_MISMATCH` | Different: every birth date the hit gives is contradicted. | `decide.py`: `decide` | `test_pipeline.py`: `test_01_account_link_and_verified_date_of_birth`; `test_rules.py`: `test_dob_mismatch_evidence` | COVERED |
| `LOCATION_MISMATCH` | Different: customer and hit share no country. | `decide.py`: `decide` | `test_pipeline.py`: `test_05_no_link_search_then_location`; `test_rules.py`: `test_location_mismatch` | COVERED |
| `NAME_MISMATCH_VERIFIED` | Different: the verified legal name matches none of the hit's names. | `decide.py`: `decide` | `test_pipeline.py`: `test_03_verified_name_beats_the_record_name` | COVERED |
| `ENTITY_TYPE_MISMATCH` | Different: a person against a company. | `decide.py`: `decide` | `test_pipeline.py`: `test_15_person_against_company` | COVERED |
| `TEMPORAL_IMPOSSIBILITY` | Different: too young, or incorporated too late, for the first dated report. | `decide.py`: `decide` | `test_pipeline.py`: `test_21_too_young_at_the_earliest_report`, `test_14_company_incorporated_after_the_report`; `test_rules.py`: `test_too_young_is_judged_on_the_birth_year` | COVERED |
| `DECEASED` | Different: the listed person died before the customer was screened. | `decide.py`: `decide` | `test_pipeline.py`: `test_16_died_before_screening`; `test_rules.py`: `test_deceased` | COVERED |
| `NAME_DOB_MATCH` | Same: name and birth date agree and nothing contradicts them. | `decide.py`: `decide` | `test_pipeline.py`: `test_04_email_link_name_and_date_agree` | COVERED |
| `NAME_DOB_LOCATION_MATCH` | Same: name, birth date and country all agree. Recorded beside `NAME_DOB_MATCH`. | `decide.py`: `decide` | `test_rules.py`: `test_brief_examples` | COVERED |
| `NAME_LOCATION_MATCH` | Same, companies only: name and country agree. | `decide.py`: `decide` | `test_pipeline.py`: `test_13_company_name_and_country` | COVERED |
| `INSUFFICIENT_DATA` | Review: nothing contradicts the hit and nothing confirms it. | `decide.py`: `decide`; `pipeline.py`: `_unprocessed` | `test_pipeline.py`: `test_08_no_record_fits`, `test_25_a_hit_whose_alert_is_missing_goes_to_review` | COVERED |
| `AMBIGUOUS_CUSTOMER_RECORD` | Review: several different people fit the alert and lead to different answers. | `decide.py`: `combine` | `test_pipeline.py`: `test_06_two_people_fit_and_disagree`; `test_rules.py`: `test_several_people` | COVERED |

## Gaps

None: every row above is `COVERED`.

## Rules of our own, on top of the policy

The policy says what the right answer is. These rules say what to do when the text is hard to
read, and each one can only turn a clearance into a review. They are listed with their reasons
in [context/decisions.md](context/decisions.md), section 3.

| Rule | Code | Tests |
|---|---|---|
| An identity check that cannot be read, or is read without its date, does not let the declared date clear a hit | `resolve.py`: `picture` | `test_pipeline.py`: `test_27_a_check_read_without_its_date_of_birth_does_not_let_the_declared_date_clear` |
| A check read out of a note clears only when the note can be believed | `resolve.py`: `believable` | `test_wording.py`: `test_a_name_the_bank_does_not_hold_supports_but_never_clears`, `test_a_document_date_in_a_check_is_not_a_birth_date` |
| A support note that is not believed never stands in front of another check | `resolve.py`: `picture` | `test_wording.py`: `test_a_later_support_note_does_not_hide_a_date_of_birth_that_agrees` |
| A country a support note only mentions blocks a clearance against that country | `decide.py`: `mentioned_ties` | `test_wording.py`: `test_a_nationality_word_in_a_support_note` |
| A country string that cannot be resolved blocks a location clearance | `decide.py`: `location_state` | `test_rules.py`: `test_unreadable_country_blocks_location_clearance` |
| A numeric date that reads two ways clears only when both readings contradict | `dates.py`: `contradicts` | `test_ambiguous_dates.py`: `test_contradicted_only_when_both_readings_are` |
| A date of birth found only by the wider reading of the profile or the search results never clears | `decide.py`: `_dob_state` | `test_watchlist_dob_recovery.py`: `test_recovered_conflicting_dob_does_not_clear_a_review`, `test_new_profile_dob_cannot_remove_the_location_exception` |
| A superseded document's country, or a place only travelled to, blocks a clearance and confirms nothing | `resolve.py`: `_travel_only_countries` | `test_country_clearances.py`: `test_superseded_document_cannot_confirm_country`, `test_travel_is_not_country_agreement_for_company` |
| A date a hit lists that cannot be read does not let the dates that were read, or a country difference, clear the hit | `dates.py`: `unread_dates`; `decide.py`: `_dob_state`, `dates_may_agree` | `test_unreadable.py`: `test_the_dates_that_can_be_read_do_not_clear`, `test_a_date_found_elsewhere_does_not_clear_either` |
| A verified date of birth that cannot be read does not let the declared date clear a hit | `resolve.py`: `picture` | `test_unreadable.py`: `test_the_declared_date_does_not_clear` |
| A note in the identity-check channel that reads as a failed check does not let the declared date clear a hit | `resolve.py`: `picture` | `test_unreadable.py`: `test_an_expiry_date_does_not_let_the_declared_date_clear`, `test_its_country_blocks_a_location_clearance_and_does_not_confirm` |
| Where a check's date of birth could not be read with confidence, a country difference does not clear a hit that gives a date | `decide.py`: `dates_may_agree` | `test_unreadable.py`: `test_a_country_difference_does_not_clear_either` |
| A date of birth that only the alert gives does not clear a hit | `resolve.py`: `picture` | `test_unreadable.py`: `test_the_screened_date_does_not_clear` |
| With no customer record, the screened details neither clear nor confirm | `resolve.py`: `screened_only` | `test_pipeline.py`: `test_08_no_record_fits` |
| A hit the system fails on is written as a review, never dropped | `pipeline.py`: `_unprocessed` | `test_pipeline.py`: `test_25_a_hit_whose_alert_is_missing_goes_to_review` |

The reading-gap integration also checks that an unread listed date blocks a contradiction
from both a wrapped profile and the original search evidence, that recovered dates retain
their limited clearance power, and that an unread check preserves weak-country cautions.
`test_unreadable.py`: `ReadingGapIntegration` covers these overlaps.
`CandidateReadingGapExplanation.test_ambiguous_review_preserves_unread_date_guard_reason`
checks that a combined candidate reason retains the unread value and its explanation while
citing both candidates.
