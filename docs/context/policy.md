# The policy, in our own words

The bank's identity procedure is `ROOM/POLICY.md` in the data room. It is the only authority on
what the right answer is. This page is a digest, so that an agent without the data room can
follow the code and the tasks. If this page and `POLICY.md` disagree, `POLICY.md` wins: report
the difference.

Do not paste the policy's text into this repo. Describe a rule in your own words instead.

## The shape of every decision

1. Work out who the customer is, from the bank's systems.
2. Work out who the listed person or company is, from the hit.
3. Compare the two. **Clear only on a contradiction. Confirm only on agreement. Otherwise review.**

An alert closes only when every hit in it is `DIFFERENT_ENTITY`. Clearing a hit that is the
customer is the worst mistake there is.

## The nine principles

| # | Principle | In short | Code |
|---|---|---|---|
| 1 | Identity, not policy | Decide whether it is the same entity. How serious the listing is does not matter | whole system |
| 2 | Know the customer first | Follow the alert's link. With no link, search the customer records | `resolve.py`: `candidates`, `search`, `fits` |
| 3 | One person, one picture | Merge the records that are one person. Keep relatives apart | `resolve.py`: `person_of`, `people` |
| 4 | Verified beats declared | The latest approved identity check gives the legal name, date of birth and document country | `resolve.py`: `picture`; `extract.py`: `read_identity_note` |
| 5 | Gather the hit's facts | Date of birth from the field, then the profile text, then search results | `watchlist.py`: `build_hit`; `extract.py` |
| 6 | Clear only on a contradiction | Five kinds: time, date of birth, location, verified name, entity type | `decide.py`: `decide` |
| 7 | Confirm only on agreement | Person: name and date of birth. Company: name and country | `decide.py`: `decide` |
| 8 | Names | How two names are compared | `names.py`: `NameRules` |
| 9 | Cite what you used | Name the records that decided it, and the customer record | `decide.py`, `pipeline.py` |

### 2. Finding the customer

- An alert shows the customer as screened, which can carry a nickname or a typo. It may also
  carry one link: an account reference, a login handle or an email.
- Follow the link. If it leads to more than one person, for example a joint account, the screened
  name and date of birth choose between them.
- With no link, a customer record fits when all of these hold: one of its names agrees with the
  screened name; its date of birth equals the screened one in every part both give; the screened
  country is its residence or nationality; the screened city appears in its city or address.
- Never use the records of a different customer.

### 3. One person, several records

- Two records are the same person when they share a phone number **and** the same full date of
  birth, or when their approved identity checks carry the same document number. The links chain:
  a record tied to either of them joins the same person.
- A shared phone or a shared address on its own proves nothing. Family members share both.
- When several different people fit an alert, decide the hit for each of them. If they all lead
  to the same decision, give that decision. If not, the answer is `REVIEW` with
  `AMBIGUOUS_CUSTOMER_RECORD`. In both cases `customer_record_id` is `AMBIGUOUS`.
- When one person has several records, any of them is accepted as `customer_record_id`.

### 4. Verified beats declared

- The person's most recent **approved** identity check is the best source for their legal name,
  date of birth and document country. The check may be a row from the KYC provider, or exist
  only as a note written by the onboarding team.
- Rejected and expired checks are not evidence of anything.
- The verified legal name outranks the name on the customer record and the screened name.

### 5. The hit's facts

- **Date of birth**, taken from the first place that has one: the hit's `dobs` field; then a
  sentence in the first paragraph of its profile notes, where an age at a date gives two possible
  birth years; then web search results for its name.
- **Search results** are mostly about namesakes. One counts only if it describes the same kind of
  listing as the hit, in a country tied to the hit. The kind of listing comes from the hit's
  primary category, or its first category. The phrases are in `extract.py`: `LISTING_PHRASES`.
- **Countries tied to a hit:** its `countries`, `nationality`, `citizenship`, the last part of
  each address, and its place of birth. Region words such as "International" are not countries.
- **Dated reports** are only the English lines in the profile notes that follow one fixed form:
  a source, then a date written as month, day and year, then the report. Other wordings do not
  count. The form is in `extract.py`: `dated_reports`.
- **Companies:** only the `dobs` field is an incorporation date.
- **Dates inside a hit's profile** are written as the provider wrote them, so a numeric date
  may be month first. `dates.py` reads `6/20/1955` as 20 June, the only way it can be read, and
  treats `04/03/1980` as a date that reads either way round.

### 6. The five contradictions

| Kind | The hit is a different entity when | Reason code |
|---|---|---|
| Type | One is a person and the other a company | `ENTITY_TYPE_MISMATCH` |
| Time | The profile gives a date of death before the customer was screened | `DECEASED` |
| Time | The customer was younger than 16 at the earliest dated report, or a company was incorporated after it | `TEMPORAL_IMPOSSIBILITY` |
| Date of birth | Every birth date the hit gives is contradicted | `DOB_MISMATCH` |
| Location | Every country tied to the customer differs from every country tied to the hit | `LOCATION_MISMATCH` |
| Name | The customer's verified legal name agrees with none of the hit's names or aliases | `NAME_MISMATCH_VERIFIED` |

The details that matter:

- **A date of birth is contradicted** when the birth years are more than one year apart, or when
  both sides give a month in the same year and the months or the days differ. One date on the
  hit that agrees is enough to stop this clearance.
- **A country difference does not clear a hit whose name and date of birth both agree.** That
  hit is `REVIEW`. A person's name with fewer than two real parts cannot confirm or clear, but
  it still agrees when every part it has matches, so it counts here too
  (`decide.py`: `short_name_agrees`).
- **The customer's countries** are the residence and nationality on all their records, the
  country of the approved identity document, and the places the notes say they lived. Codes and
  nationalities count as countries. A territory is its own country.
- **Only a verified name can contradict.** A name on the customer record that fails to match
  proves nothing, because it may be a nickname.
- When several contradictions hold, any of their codes is accepted. Our code reports them in the
  order of the table above and uses the first as the main one.

### 7. Agreement

- Dates of birth agree when the customer's birth year is one of the hit's possible years and
  every part both sides give is equal. A year on its own can agree with a full date.
- A person is confirmed when the name and the date of birth agree and nothing contradicts:
  `NAME_DOB_MATCH`, or `NAME_DOB_LOCATION_MATCH` when a country agrees too.
- A company is confirmed when the name and a country agree and nothing contradicts:
  `NAME_LOCATION_MATCH`.
- Everything else is `REVIEW` with `INSUFFICIENT_DATA`.

### 8. Comparing names

- Ignore case, accents, punctuation and anything in brackets. A single letter is an initial,
  not a name part. Each distinct part counts once.
- Two parts match when they are identical, when the variants file lists them together, when one
  is the other written together or apart, or when they are within a small number of letter
  edits. The edit limit depends on the length of the shorter part, and short parts must be
  identical. The exact limits are in `names.py`: `part_match`.
- Two names agree when at least two parts match, or when every part of the shorter name matches.
- Aliases and nicknames count as names.
- Placeholders such as NA, TEST or UNKNOWN are not name parts. A person whose names have fewer
  than two real parts can be neither confirmed nor cleared on name.
- For companies, legal forms such as Ltd or GmbH are not name parts. The list is in the
  variants file.

## The rules that apply to every fact

- **Unknown stays unknown.** A missing field is not a mismatch. Neither is the missing part of a
  partial date. Never fill a gap with a guess.
- **A rejected check is not evidence**, in either direction.
- **Build for the principles, not for these files.** The unseen set words its free text
  differently.

## Where our code is stricter than the policy

These are deliberate. Each one can cost a review and can never cost a clearance.

| Situation | What the code does | Where |
|---|---|---|
| An identity check written as a note cannot be read, or is read without its date of birth | The declared date of birth may still agree with a hit, but it may not clear one | `Customer.dob_can_clear` |
| A check written as a note cannot be believed: outside the identity-check channel it names no document, its legal name shares no part with any name the bank holds for the customer, or a person's date of birth falls within 14 years of the note | The note is still read and may support a match. It may not clear on name or on date of birth. A support note read that way never stands in front of another check; one in the identity-check channel keeps its place as the latest | `resolve.py`: `Resolver.believable`, and `standing` in `Resolver.picture` |
| A country string cannot be resolved | It blocks a location clearance instead of being ignored | `location_state` |
| A support note only mentions one of the hit's countries: as a nationality word, or in a note set aside as a failed check | It is not a shared country, but it blocks a location clearance against that country | `decide.py`: `mentioned_ties`, `location_state` |
| No customer record is found | The screened details can neither clear nor confirm. Only the entity type and a date of death, which need no record, still decide | `resolve.py`: `screened_only` |
| A legal name or a date of birth was read by a model and not by the rules | It may support a match but may not clear, unless the reader is set to `enforce` | `Customer.name_can_clear`, `Customer.dob_can_clear` |
| A hit cannot be processed at all | It gets a `REVIEW` line, never a silent clearance | `pipeline.py`: `_unprocessed` |
| A numeric date reads either way round, such as 04/03/1980 | It is read day first for agreement, as before. A date-of-birth contradiction, a date of death before screening and a report before a company's incorporation must hold under both readings to clear | `dates.py`: `readings`, `contradicts`, `surely_before` |
| One of the dates a hit lists cannot be read | It is kept as unknown, not dropped. The dates that could be read may still agree with the customer's but may not clear, and a date found in the notes or the search results may not clear in its place. Where the name agrees, a country difference does not clear either: the unread date may be the one that agrees. A year no date here can have, such as 1340 from another calendar, cannot agree and takes no part, as before | `dates.py`: `unread_dates`; `decide.py`: `dob_state`, `dates_may_agree` |
| The provider's verified date of birth cannot be read | The declared date of birth may still agree with a hit, but it may not clear one | `resolve.py`: `Resolver.picture` |
| A note in the identity-check channel reads as a failed check | Nothing it says is used, as before. A check that passed can read that way too, for example when it gives the document's expiry date, so the declared date of birth may still agree with a hit but may not clear one, and a country the note names blocks a location clearance against that country | `resolve.py`: `FAILED_CHECK_NOTES_NEVER_CLEAR` |
| A check gives the customer a date of birth that could not be read with confidence (any of the rows about checks above), the hit gives a date, and the name agrees | A country difference does not clear the hit: the date the bank verified may agree with the hit's, and a country difference does not clear a hit whose name and date of birth agree | `Customer.dob_in_doubt`; `decide.py`: `dates_may_agree` |
| The customer's only date of birth is the one on the alert | It may agree with a hit, but it may not clear one: no record backs it. A country difference still clears, because no check is hiding another date | `resolve.py`: `Resolver.picture` |
| The customer's age at the earliest dated report | It is worked out from the birth year alone, so a customer aged 15 on the day and 16 by birth year is not cleared | `decide.py`: `decide`, `MIN_AGE` |
| A date of death | Only the hit's `deceased_date` field is read, not the profile text | `watchlist.py`: `build_hit` |

## Where our code reads the policy more narrowly

Two readings are narrower than the policy's words. Neither is purely stricter, so they are
listed apart from the table above.

| The policy says | What the code does | What it can cost |
|---|---|---|
| A hit's date of birth may be given by a sentence in the first paragraph of its profile notes | `extract.py`: `profile_birth` reads only the opening line of that paragraph. A date on a later line is missed, and the search results are used in its place | The search results give two possible years where the profile gives a full date, so a customer born in the same year and another month can be matched where the full date would clear. `H-2C6B2E` and `H-FE02A6` share the one development profile whose first paragraph gives a date after its opening line |
| The customer is tied to the places the notes say they lived | `resolve.py`: `Resolver.picture` ties the customer to any country a support note names outright | For a person it can only hold a location clearance back. For a company it can confirm a match on the name and that country |

## The eleven reason codes

A reason code must belong to its decision, or the line is invalid.

| Decision | Codes |
|---|---|
| `DIFFERENT_ENTITY` | `TEMPORAL_IMPOSSIBILITY`, `DOB_MISMATCH`, `LOCATION_MISMATCH`, `NAME_MISMATCH_VERIFIED`, `ENTITY_TYPE_MISMATCH`, `DECEASED` |
| `SAME_ENTITY` | `NAME_DOB_LOCATION_MATCH`, `NAME_DOB_MATCH`, `NAME_LOCATION_MATCH` (companies only) |
| `REVIEW` | `INSUFFICIENT_DATA`, `AMBIGUOUS_CUSTOMER_RECORD` |

## What evidence to cite

Cite the records that decided the hit, not everything that was read. The organisers compare the
list with their own.

| Ground | Evidence cited |
|---|---|
| Date of birth | The check or note that gave the customer's date, plus the search result when the hit's date came from one |
| Location mismatch | Every record that ties the customer to a country |
| Location agreement | The records that give the shared country |
| Verified name mismatch | The identity check that gave the legal name |
| Date of death | The hit's own field, written `H-xxxxxx#deceased_date` |
| Name agreement | Nothing. It is stated in the reason but rests on no single record |

On the 50 practice labels our evidence list equals the reference list every time.
