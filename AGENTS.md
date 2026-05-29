the app extracts structured json from 2081272 ACP-127 telegram messages using python rebulk lib

read docs/rebulk.md for documentation
use `pydoc3 rebulk` to lookup function calls
for examples of rebulk usage look at /usr/lib/python3/dist-packages/guessit

to tackle the large amount of messy data the app MUST:
- calculate byte coverage across the input document (percentage how much input text was matched)
- track the match coverage across all input documents (percentage how many documents had a match)

the data is extracted with chains of patterns that are combined in a depedency tree of rebulk Rules

for each extract field we define a pattern in a dedicated file

# input structure

the details of acp-127 are described in docs/acp127g.txt
the following describes each field in order of dependency

---
the input is split into two parts with the strings

r"\s+Message Text"

r"\s+Message Attributes"

these strings MUST only match once per document and are the root of the dependency tree expressed as rebulk Rule
the acp-127 message content is located between "Message Text" and "Message Attributes"

---

"Message Attributes" follows a list of atrributes in "key: value" format. 
SOME attribute values cross multiple lines
Each attribute MUST be handled as indiviudal field for dependency checks
See ATTRIBUTES.md for possible values and counts of each attribute

---
r"^Locator:" attribute indicates if the content after "Message Text" contains a acp-127 message or errors
r"TEXT ON-LINE" MUST exist for acp-127 extraction 
---
Automatic Decaptioning
Capture Date
Channel Indicators
Current Classification
Concepts
Control Number
Copy
Draft Date
Decaption Date
Decaption Note
Disposition Action
Disposition Approved on Date
Disposition Authority
Disposition Case Number
Disposition Comment
Disposition Date
Disposition Event
Disposition History
Disposition Reason
Disposition Remarks
Document Number
Document Source
Document Unique ID
Drafter
Enclosure
Executive Order
Errors
Film Number
From
Handling Restrictions
Image Path
ISecure
Legacy Key
Line Count
Locator
Office
Original Classification
Original Handling Restrictions
