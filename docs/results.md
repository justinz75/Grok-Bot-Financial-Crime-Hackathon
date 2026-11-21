# Results

Every number on this page was printed by the command in its heading, run on 21 November 2026
at about 15:05 London time, on the code of `main` at that time. `DATA` is the development
folder. Nothing here is rounded or retyped: the blocks are the commands' own output.

## The layers: `python tools/ablate.py DATA --runs 5 --stress`

No OpenRouter key was available, so the settings that need a language model were skipped. They
are still unmeasured against a real model.

```
model: none available

DATA AS GIVEN (compared with the rules alone)
setting                    diff same  rev | changed to review NEW CLEAR | right unsafe score | unstable  secs
rules only                  464  125  230 |       0         0         0 |    50      0 100.0 |        -   7.4
score on                    464  125  230 |       0         0         0 |    50      0 100.0 |        -   8.7
score enforce               464  125  230 |       0         0         0 |    50      0 100.0 |        -   8.4
briefing on                 464  125  230 |       0         0         0 |    50      0 100.0 |        -   8.4
reviewer on (shadow)       skipped: needs OPENROUTER_API_KEY (or SCREENING_MODEL=fake for a dry run)
reviewer enforce           skipped: needs OPENROUTER_API_KEY (or SCREENING_MODEL=fake for a dry run)
reader on (cautious)       skipped: needs OPENROUTER_API_KEY (or SCREENING_MODEL=fake for a dry run)
reader enforce (trusted)   skipped: needs OPENROUTER_API_KEY (or SCREENING_MODEL=fake for a dry run)
all on                     skipped: needs OPENROUTER_API_KEY (or SCREENING_MODEL=fake for a dry run)
  score on
      score bands: inconclusive 294, some evidence of the same 277, some evidence of a different one 117, strong evidence of the same 98, strong evidence of a different one 95
      clearances where the score leans the other way: 0
  score enforce
      score bands: inconclusive 294, some evidence of the same 277, some evidence of a different one 117, strong evidence of the same 98, strong evidence of a different one 95
      clearances where the score leans the other way: 0
  briefing on
      briefings written: 881, with a caveat: 509
new clearances created by any layer: none

IDENTITY NOTES WITHOUT CAPITALS (compared with the rules on the data as given)
setting                    diff same  rev | changed to review NEW CLEAR | right unsafe score | unstable  secs
rules only                  430  135  254 |      36        24         0 |    49      0  97.2 |        -   7.6
score on                    430  135  254 |      36        24         0 |    49      0  97.2 |        -   8.4
score enforce               430  135  254 |      36        24         0 |    49      0  97.2 |        -   7.7
briefing on                 430  135  254 |      36        24         0 |    49      0  97.2 |        -   7.7
reviewer on (shadow)       skipped: needs OPENROUTER_API_KEY (or SCREENING_MODEL=fake for a dry run)
reviewer enforce           skipped: needs OPENROUTER_API_KEY (or SCREENING_MODEL=fake for a dry run)
reader on (cautious)       skipped: needs OPENROUTER_API_KEY (or SCREENING_MODEL=fake for a dry run)
reader enforce (trusted)   skipped: needs OPENROUTER_API_KEY (or SCREENING_MODEL=fake for a dry run)
all on                     skipped: needs OPENROUTER_API_KEY (or SCREENING_MODEL=fake for a dry run)
  score on
      score bands: some evidence of the same 306, inconclusive 298, strong evidence of the same 110, some evidence of a different one 84, strong evidence of a different one 83
      clearances where the score leans the other way: 0
  score enforce
      score bands: some evidence of the same 306, inconclusive 298, strong evidence of the same 110, some evidence of a different one 84, strong evidence of a different one 83
      clearances where the score leans the other way: 0
  briefing on
      briefings written: 881, with a caveat: 513
new clearances created by any layer: none
```

- No setting changed a decision compared with the rules alone: the `changed` column is 0 for
  the score layer, on and enforcing, and for the briefing layer.
- Stability between runs is measured by this tool for the model settings only, and none ran.
  For the settings that did run, `python tools/repro.py DATA --runs 5 --strict` starts five fresh
  processes and reports the scored files and the explain files byte-identical.
- No setting created a clearance. With the capitals taken out of the identity notes, the rules
  alone change 36 decisions, 24 of them to review, none to a clearance, and score 49 of 50.

## Text made harder to read: `python tools/stress.py DATA`

Each row damages the development folder one way and runs the system again. The last column is
the one that must be 0: a hit that was a review or a match and became a clearance.

```
case                                     same  to rev.    other  NEW CLEAR
names in Title Case                       783       25       11          0
names in lower case                       784       24       11          0
Title Case, no birth words                739       69       11          0
checks say nothing                        739       69       11          0
checks filed under another channel        819        0        0          0
ages reworded                             819        0        0          0
countries reworded                        819        0        0          0
rows shuffled                             819        0        0          0
optional fields dropped                   818        0        1          0
support notes gain capitals               819        0        0          0
checks gain a status in capitals          805       13        1          0
support notes gain a year                 819        0        0          0
support notes read as failed checks       819        0        0          0
countries as nationalities                819        0        0          0

new clearances caused by harder text: none
```

The first nine rows take text away or reword it. The last five add text that can be misread.
Before the rules for doubtful notes and mentioned countries, those five turned 129, 10, 28, 41
and 40 reviews or matches into clearances.

## A real sanctions list: `python tools/public_test.py --people 30000 --companies 30000`

The list is the OpenSanctions consolidated export described in
[data-sources.md](data-sources.md). It stays local. The test takes every person with a birth date
and a country and every organisation with a country, and for each one invents customers whose
right answer follows from how they were built.

```
list: 22772 people with a birth date and a country, 24265 organisations with a country
left out: 0 people with no birth date between 1900 and 2026. Of those sampled, 5 list another date first
sampled: 22772 people (21 with a one-part name) and 24265 organisations, 232142 hits, decided in 260.0s

                       built as        the answer that follows                 cases as built to review to match  CLEARED
people                 same            SAME_ENTITY NAME_DOB_MATCH              22751    22751         0        0        0
people                 other date      DIFFERENT_ENTITY DOB_MISMATCH           22751    22751         0        0        0
people                 no date         REVIEW INSUFFICIENT_DATA                22751    22751         0        0        0
people                 other country   REVIEW INSUFFICIENT_DATA                22751    22744         0        7        0
people                 dateless hit    DIFFERENT_ENTITY LOCATION_MISMATCH      22751    22744         7        0        0
people                 dateless, home  REVIEW INSUFFICIENT_DATA                22751    22751         0        0        0
people                 other name      DIFFERENT_ENTITY NAME_MISMATCH_VERIFIED  22715    22689        21        5        0
people, one-part name  same            REVIEW INSUFFICIENT_DATA                   21       21         0        0        0
people, one-part name  other date      DIFFERENT_ENTITY DOB_MISMATCH              21       21         0        0        0
people, one-part name  no date         REVIEW INSUFFICIENT_DATA                   21       21         0        0        0
people, one-part name  other country   REVIEW INSUFFICIENT_DATA                   21       21         0        0        0
people, one-part name  dateless hit    DIFFERENT_ENTITY LOCATION_MISMATCH         21       21         0        0        0
people, one-part name  dateless, home  REVIEW INSUFFICIENT_DATA                   21       21         0        0        0
companies              same            SAME_ENTITY NAME_LOCATION_MATCH         24265    24215        50        0        0
companies              other country   DIFFERENT_ENTITY LOCATION_MISMATCH      24265    24205        60        0        0
companies              a person        DIFFERENT_ENTITY ENTITY_TYPE_MISMATCH   24265    24265         0        0        0

231992 of 232142 came out as built; 138 went to review instead, 12 to a match
cleared when it should not be: 0
```

What the rows that did not come out as built are:

- **To review instead of a match or a clearance.** Organisation names made only of initials
  and a legal form, which the policy does not count as name parts, and country codes the
  system does not know, such as the codes for regions and for states that no longer exist. An
  unknown country blocks a location clearance on purpose.
- **A match where a review was built** (other country): the hit lists a country the system does
  not know, so the countries cannot be said to differ, and name and date of birth agree.
- **A match where a clearance was built** (other name): the unrelated name agrees with one of
  the hit's names under the policy's own rules, for example through two shared parts where one
  is a particle such as "al", and the date of birth was copied from the profile.
- **To review where a clearance was built** (other name): the unrelated name has one real
  part, so it cannot clear on name.

This test found one gap in the rules, now closed. A customer with a one-part name that agrees
with the hit's, and an agreeing date of birth, was cleared on a country difference. The policy
says such a name cannot confirm or clear on name; it still agrees, so the hit is a review.
Before the fix the row `people, one-part name / other country` read 0 as built and 21 cleared.

Two limits the test also showed are listed in [system/README.md](../system/README.md) under
"What is missing": a birth year from another calendar is not read as a date, and name
particles count as name parts.
