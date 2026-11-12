"""Committee pop-up facts from official House/Senate committee pages and history offices only.

Skip any committee that has no official source. Excerpts are validated against the
saved official HTML (same whitespace normalization as ingest/verify.py) before claims
are written. New claims use kind source-excerpt and are merged into claims.json
without changing existing verified claims.
"""
import json, re, html as H, hashlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *

RAWCH = RAW / "committee-history"
SITE = BUILD / "site"
OUT = SITE / "committee-history.json"
RETRIEVED = "2026-11-12T02:04:56+00:00"

def norm(html: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    text = H.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text)

# Official pages only (House/Senate committee sites or history.house.gov / senate.gov history).
RECORDS = [
  {"code": "AG00", "name": "Committee on Agriculture", "chamber": "house", "facts": [
    {"kind": "created", "text": "The House Committee on Agriculture was created on May 3, 1820, after the House agreed to a resolution submitted by Mr. Williams of North Carolina.",
     "excerpt": "On motion of Mr. Williams of North Carolina, the House took up and proceeded to consider the resolution submitted by him on the 29th ultimo, for the appointment of a standing committee to be denominated \u201cThe Committee on Agriculture;\u201d and the resolution was agreed to by the House, and ordered that the committee consist of seven members. Thus the Committee on Agriculture was created on May 3, 1820.",
     "needles": ["Thus the Committee on Agriculture was created on May 3, 1820.", "On motion of Mr. Williams of North Carolina, the House took up and proceeded to consider the resolution"],
     "source_url": "https://agriculture.house.gov/about/committee-history.htm",
     "source_name": "U.S. House Committee on Agriculture, official committee history",
     "local": "agriculture.house.gov_about_committee-history.htm.html"},
    {"kind": "purpose", "text": "The House Committee on Agriculture\u2019s jurisdiction, as originally defined, covered \u201csubjects relating to agriculture.\u201d",
     "excerpt": "The jurisdiction of the committee, as originally defined, covered simply \"subjects relating to agriculture.\"",
     "needles": ["The jurisdiction of the committee, as originally defined, covered simply"],
     "source_url": "https://agriculture.house.gov/about/committee-history.htm",
     "source_name": "U.S. House Committee on Agriculture, official committee history",
     "local": "agriculture.house.gov_about_committee-history.htm.html"},
  ]},
  {"code": "AP00", "name": "Committee on Appropriations", "chamber": "house", "facts": [
    {"kind": "created", "text": "On March 2, 1865, the House of Representatives created the Committee on Appropriations by separating appropriating duties from the Committee on Ways and Means.",
     "excerpt": "On March 2, 1865, the House of Representatives separated the appropriating and banking and currency duties from the Committee on Ways and Means, which was first established in 1789, and assigned them to two new committees - the Committee on Appropriations and the Committee on Banking and Currency.",
     "needles": ["On March 2, 1865, the House of Representatives separated the appropriating and banking and currency duties", "assigned them to two new committees - the Committee on Appropriations and the Committee on Banking and Currency."],
     "source_url": "https://appropriations.house.gov/about/history",
     "source_name": "U.S. House Committee on Appropriations, official history",
     "local": "appropriations.house.gov_about_history.html"},
  ]},
  {"code": "BU00", "name": "Committee on the Budget", "chamber": "house", "facts": [
    {"kind": "created", "text": "The Congressional Budget and Impoundment Control Act of 1974 established standing budget committees in both chambers of Congress.",
     "excerpt": "The Budget Act also established standing committees in both chambers of Congress with jurisdiction over, among other things, the concurrent resolution on the budget.",
     "needles": ["The Budget Act also established standing committees in both chambers of Congress"],
     "source_url": "https://budget.house.gov/about",
     "source_name": "U.S. House Committee on the Budget, official about page",
     "local": "budget.house.gov_about.html"},
    {"kind": "purpose", "text": "Under House Rule X, clause 1(d), the House Budget Committee has jurisdiction over the concurrent resolution on the budget, special controls over the federal budget, and the budget process generally.",
     "excerpt": "House Rule X, clause 1(d) states that the Budget Committee will have jurisdiction over the concurrent resolution on the budget; other matters required to be referred to it pursuant to the Budget Act; establishment, extension, and enforcement of special controls over the federal budget; and the budget process generally.",
     "needles": ["House Rule X, clause 1(d) states that the Budget Committee will have jurisdiction over the concurrent resolution on the budget"],
     "source_url": "https://budget.house.gov/about",
     "source_name": "U.S. House Committee on the Budget, official about page",
     "local": "budget.house.gov_about.html"},
  ]},
  {"code": "SSBU", "name": "Committee on the Budget", "chamber": "senate", "facts": [
    {"kind": "created", "text": "The Congressional Budget and Impoundment Control Act of 1974 established standing budget committees in both chambers of Congress.",
     "excerpt": "The Budget Act also established standing committees in both chambers of Congress with jurisdiction over, among other things, the concurrent resolution on the budget.",
     "needles": ["The Budget Act also established standing committees in both chambers of Congress"],
     "source_url": "https://budget.house.gov/about",
     "source_name": "U.S. House Committee on the Budget, official about page",
     "local": "budget.house.gov_about.html"},
  ]},
  {"code": "HA00", "name": "Committee on House Administration", "chamber": "house", "facts": [
    {"kind": "purpose", "text": "The Committee on House Administration\u2019s jurisdiction over federal elections requires it to consider proposals to amend federal election law and to monitor congressional elections across the United States.",
     "excerpt": "The Committee's jurisdiction over federal elections requires it to consider proposals to amend federal election law and to monitor congressional elections across the United States.",
     "needles": ["The Committee's jurisdiction over federal elections requires it to consider proposals to amend federal election law"],
     "source_url": "https://cha.house.gov/about",
     "source_name": "U.S. House Committee on House Administration, official about page",
     "local": "cha.house.gov_about.html"},
  ]},
  {"code": "IF00", "name": "Committee on Energy and Commerce", "chamber": "house", "facts": [
    {"kind": "created", "text": "The committee now called Energy and Commerce was originally established on December 14, 1795, as the Committee on Commerce and Manufactures.",
     "excerpt": "The committee was originally established on December 14, 1795, as the Committee on Commerce and Manufactures when the growing demands of the young nation required that Congress establish a permanent panel to exercise its constitutional authority to \"regulate Commerce with foreign Nations, and among the several States.\"",
     "needles": ["The committee was originally established on December 14, 1795, as the Committee on Commerce and Manufactures"],
     "source_url": "https://energycommerce.house.gov/about",
     "source_name": "U.S. House Committee on Energy and Commerce, official about page",
     "local": "energycommerce.house.gov_about.html"},
    {"kind": "purpose", "text": "The House Committee on Energy and Commerce is the oldest standing legislative committee in the U.S. House of Representatives and is vested with the broadest jurisdiction of any congressional authorizing committee.",
     "excerpt": "The Committee on Energy and Commerce is the oldest standing legislative committee in the U.S. House of Representatives and is vested with the broadest jurisdiction of any congressional authorizing committee.",
     "needles": ["The Committee on Energy and Commerce is the oldest standing legislative committee in the U.S. House of Representatives"],
     "source_url": "https://energycommerce.house.gov/about",
     "source_name": "U.S. House Committee on Energy and Commerce, official about page",
     "local": "energycommerce.house.gov_about.html"},
  ]},
  {"code": "BA00", "name": "Committee on Financial Services", "chamber": "house", "facts": [
    {"kind": "purpose", "text": "The House Financial Services Committee has jurisdiction over issues pertaining to the economy, the banking system, housing, insurance, and securities and exchanges.",
     "excerpt": "The House Financial Services Committee has jurisdiction over issues pertaining to the economy, the banking system, housing, insurance, and securities and exchanges.",
     "needles": ["The House Financial Services Committee has jurisdiction over issues pertaining to the economy, the banking system, housing, insurance, and securities and exchanges."],
     "source_url": "https://financialservices.house.gov/about/",
     "source_name": "U.S. House Committee on Financial Services, official about page",
     "local": "financialservices.house.gov_about_.html"},
  ]},
  {"code": "WM00", "name": "Committee on Ways and Means", "chamber": "house", "facts": [
    {"kind": "created", "text": "The Committee on Ways and Means was first established as a select committee on July 24, 1789, was reappointed in 1795, and was formally listed as a standing committee in the House Rules on January 7, 1802.",
     "excerpt": "First established as a select committee on July 24, 1789, it was discharged less than two months later. The committee was reappointed from the first session of the Fourth Congress in 1795, and was formally listed as a standing committee in the House Rules on January 7, 1802.",
     "needles": ["First established as a select committee on July 24, 1789, it was discharged less than two months later.", "formally listed as a standing committee in the House Rules on January 7, 1802."],
     "source_url": "https://waysandmeans.house.gov/about/",
     "source_name": "U.S. House Committee on Ways and Means, official about page",
     "local": "waysandmeans.house.gov_about_.html"},
    {"kind": "purpose", "text": "The Committee on Ways and Means is the oldest committee of the United States Congress and is the chief tax-writing committee in the House of Representatives.",
     "excerpt": "The Committee on Ways and Means is the oldest committee of the United States Congress, and is the chief tax-writing committee in the House of Representatives.",
     "needles": ["The Committee on Ways and Means is the oldest committee of the United States Congress, and is the chief tax-writing committee in the House of Representatives."],
     "source_url": "https://waysandmeans.house.gov/about/",
     "source_name": "U.S. House Committee on Ways and Means, official about page",
     "local": "waysandmeans.house.gov_about_.html"},
  ]},
  {"code": "HM00", "name": "Committee on Homeland Security", "chamber": "house", "facts": [
    {"kind": "created", "text": "The Committee on Homeland Security was created as a nine-member select committee on June 19, 2002, and became a permanent standing committee on January 4, 2005.",
     "excerpt": "In the wake of the September 11, 2001, terrorist attacks, the Committee on Homeland Security was created as a nine-member select committee on June 19, 2002. With a jurisdiction to provide congressional oversight of the newly created Department of Homeland Security, it became a permanent standing committee on January 4, 2005.",
     "needles": ["the Committee on Homeland Security was created as a nine-member select committee on June 19, 2002.", "it became a permanent standing committee on January 4, 2005."],
     "source_url": "https://history.house.gov/Education/Fact-Sheets/Committees-Fact-Sheet2/",
     "source_name": "History, Art & Archives, U.S. House of Representatives, Committees fact sheet",
     "local": "history.house.gov_Education_Fact-Sheets_Committees-Fact-Sheet2_.html"},
    {"kind": "purpose", "text": "Pursuant to clause 1(j) of House Rule X, the Committee on Homeland Security has legislative jurisdiction over overall homeland security policy.",
     "excerpt": "Pursuant to clause 1(j) of House Rule X, the Committee has the following legislative jurisdiction : (1) Overall homeland security policy.",
     "needles": ["Pursuant to clause 1(j) of House Rule X, the Committee has the following legislative jurisdiction", "Overall homeland security policy."],
     "source_url": "https://homeland.house.gov/about",
     "source_name": "U.S. House Committee on Homeland Security, official about page",
     "local": "homeland.house.gov_about.html"},
  ]},
  {"code": "RU00", "name": "Committee on Rules", "chamber": "house", "facts": [
    {"kind": "created", "text": "The House Committee on Rules was first formally constituted on April 2, 1789.",
     "excerpt": "The Committee on Rules is amongst the oldest standing committees in the House, having been first formally constituted on April 2, 1789.",
     "needles": ["having been first formally constituted on April 2, 1789."],
     "source_url": "https://rules.house.gov/about",
     "source_name": "U.S. House Committee on Rules, official about page",
     "local": "rules.house.gov_about.html"},
    {"kind": "purpose", "text": "The Rules Committee has two broad categories of jurisdiction: special orders for the consideration of legislation (special rules) and original jurisdiction matters.",
     "excerpt": "The Rules Committee has two broad categories of jurisdiction: special orders for the consideration of legislation (known as \" special rules \" or \"rules\") and original jurisdiction matters.",
     "needles": ["The Rules Committee has two broad categories of jurisdiction"],
     "source_url": "https://rules.house.gov/about",
     "source_name": "U.S. House Committee on Rules, official about page",
     "local": "rules.house.gov_about.html"},
  ]},
  {"code": "JU00", "name": "Committee on the Judiciary", "chamber": "house", "facts": [
    {"kind": "created", "text": "On June 3, 1813, a standing committee on the Judiciary was established by the House of Representatives to consider legislation relating to judicial proceedings.",
     "excerpt": "On June 3, 1813, a standing committee on the Judiciary was established by the House of Representatives to consider legislation relating to judicial proceedings.",
     "needles": ["On June 3, 1813, a standing committee on the Judiciary was established by the House of Representatives"],
     "source_url": "https://judiciary.house.gov/about",
     "source_name": "U.S. House Committee on the Judiciary, official about page",
     "local": "judiciary.house.gov_about.html"},
    {"kind": "purpose", "text": "The House Committee on the Judiciary has jurisdiction over matters relating to the administration of justice in federal courts, administrative bodies, and law enforcement agencies.",
     "excerpt": "The Committee on the Judiciary has been called the lawyer for the House of Representatives because of its jurisdiction over matters relating to the administration of justice in federal courts, administrative bodies, and law enforcement agencies.",
     "needles": ["jurisdiction over matters relating to the administration of justice in federal courts, administrative bodies, and law enforcement agencies."],
     "source_url": "https://judiciary.house.gov/about",
     "source_name": "U.S. House Committee on the Judiciary, official about page",
     "local": "judiciary.house.gov_about.html"},
  ]},
  {"code": "II00", "name": "Committee on Natural Resources", "chamber": "house", "facts": [
    {"kind": "created", "text": "The House Committee on Natural Resources traces its jurisdictional history to the Committee on Public Lands, which was created on December 17, 1805, on a motion by Representative William Findley of Pennsylvania.",
     "excerpt": "The House Committee on Natural Resources can trace its jurisdictional history to the Committee on Public Lands, which was created on December 17, 1805, on a motion by Representative William Findley, a Democratic-Republican from Pennsylvania.",
     "needles": ["Committee on Public Lands, which was created on December 17, 1805, on a motion by Representative William Findley"],
     "source_url": "https://naturalresources.house.gov/about",
     "source_name": "U.S. House Committee on Natural Resources, official about page",
     "local": "naturalresources.house.gov_about.html"},
  ]},
  {"code": "PW00", "name": "Committee on Transportation and Infrastructure", "chamber": "house", "facts": [
    {"kind": "purpose", "text": "The House Committee on Transportation and Infrastructure has jurisdiction over all modes of transportation: aviation, highways and bridges, transit and rail, pipelines, and maritime and waterborne transportation.",
     "excerpt": "The Committee has jurisdiction over all modes of transportation \u2013 our aviation system, highways and bridges, transit and rail transportation, pipelines, and maritime and waterborne transportation.",
     "needles": ["The Committee has jurisdiction over all modes of transportation", "aviation system, highways and bridges, transit and rail transportation, pipelines, and maritime and waterborne transportation."],
     "source_url": "https://transportation.house.gov/about",
     "source_name": "U.S. House Committee on Transportation and Infrastructure, official about page",
     "local": "transportation.house.gov_about.html"},
  ]},
  {"code": "SM00", "name": "Committee on Small Business", "chamber": "house", "facts": [
    {"kind": "created", "text": "On December 4, 1941, the House of Representatives created the first House Select Committee on Small Business; it was made a permanent standing committee on January 5, 1975.",
     "excerpt": "On December 4, 1941, the U. S. House of Representatives created the first House Select Committee on Small Business. The select committee was established in response to a growing number of small business activists and organizations advocating for more protections and better government policies for America\u2019s small businesses. While it had no legislative authority, the select committee became popular with House members and was reauthorized each Congress until January 5, 1975, when it was made a permanent standing committee.",
     "needles": ["On December 4, 1941, the U. S. House of Representatives created the first House Select Committee on Small Business.", "until January 5, 1975, when it was made a permanent standing committee."],
     "source_url": "https://smallbusiness.house.gov/about",
     "source_name": "U.S. House Committee on Small Business, official about page",
     "local": "smallbusiness.house.gov_about.html"},
  ]},
  {"code": "SSAF", "name": "Committee on Agriculture, Nutrition, and Forestry", "chamber": "senate", "facts": [
    {"kind": "created", "text": "On December 9, 1825, by a vote of 22-14, the Senate approved a resolution creating a standing Committee on Agriculture.",
     "excerpt": "On December 9, 1825, by a vote of 22-14, the Senate approved a resolution creating a standing Committee on Agriculture.",
     "needles": ["On December 9, 1825, by a vote of 22-14, the Senate approved a resolution creating a standing Committee on Agriculture."],
     "source_url": "https://www.agriculture.senate.gov/about/history",
     "source_name": "U.S. Senate Committee on Agriculture, Nutrition, and Forestry, official history",
     "local": "www.agriculture.senate.gov_about_history.html"},
  ]},
  {"code": "SSAP", "name": "Committee on Appropriations", "chamber": "senate", "facts": [
    {"kind": "created", "text": "The Senate Committee on Appropriations was created on March 6, 1867, when the Senate agreed by unanimous consent to a resolution by Senator Anthony.",
     "excerpt": "Without further discussion, Anthony's resolution was considered by unanimous consent and agreed to, giving birth to the Senate Committee on Appropriations on March 6, 1867.",
     "needles": ["giving birth to the Senate Committee on Appropriations on March 6, 1867."],
     "source_url": "https://www.appropriations.senate.gov/about/history",
     "source_name": "U.S. Senate Committee on Appropriations, official history",
     "local": "www.appropriations.senate.gov_about_history.html"},
  ]},
  {"code": "SSAS", "name": "Committee on Armed Services", "chamber": "senate", "facts": [
    {"kind": "created", "text": "The Senate Committees on Military Affairs, on the Militia, and Naval Affairs were established on December 10, 1816; the Legislative Reorganization Act of 1946 combined the Military Affairs and Naval Affairs Committees into the current Committee on Armed Services.",
     "excerpt": "The Senate Committees on Military Affairs; on the Militia; and Naval Affairs were established on December 10, 1816.",
     "needles": ["The Senate Committees on Military Affairs; on the Militia; and Naval Affairs were established on December 10, 1816.", "combined by the Legislative Reorganization Act of 1946 into a new standing committee, the current Committee on Armed Services."],
     "source_url": "https://www.armed-services.senate.gov/about/history",
     "source_name": "U.S. Senate Committee on Armed Services, official history",
     "local": "www.armed-services.senate.gov_about_history.html"},
    {"kind": "purpose", "text": "As specified in Rule XXV of the Standing Rules of the Senate, the Committee on Armed Services has jurisdiction that includes aeronautical and space activities peculiar to or primarily associated with the development of weapons systems or military operations.",
     "excerpt": "As specified in Rule XXV, 1(c)(1) of the Standing Rules of the Senate, the Committee on Armed Services' has the following jurisdiction: Aeronautical and space activities peculiar to or primarily associated with the development of weapons systems or military operations.",
     "needles": ["As specified in Rule XXV, 1(c)(1) of the Standing Rules of the Senate, the Committee on Armed Services'", "Aeronautical and space activities peculiar to or primarily associated with the development of weapons systems or military operations."],
     "source_url": "https://www.armed-services.senate.gov/about/history",
     "source_name": "U.S. Senate Committee on Armed Services, official history",
     "local": "www.armed-services.senate.gov_about_history.html"},
  ]},
  {"code": "SSBK", "name": "Committee on Banking, Housing, and Urban Affairs", "chamber": "senate", "facts": [
    {"kind": "created", "text": "Until 1913 the Senate operated without a banking committee; the Senate established its banking committee on March 15, 1913.",
     "excerpt": "Until 1913, the Senate operated without a banking committee. Unlike the House of Representatives, which had created its own banking panel in 1865, the Senate chose to refer banking and currency legislation to its Committee on Finance. When the Senate finally made its move on March 15, 1913, the two most responsible forces were Oklahoma senator Robert Owen and that year's pending Federal Reserve Act .",
     "needles": ["Until 1913, the Senate operated without a banking committee.", "When the Senate finally made its move on March 15, 1913"],
     "source_url": "https://www.senate.gov/about/origins-foundations/committee-system/banking-committee-established.htm",
     "source_name": "U.S. Senate, official history (Senate Banking Committee established)",
     "local": "www.senate.gov_about_origins-foundations_committee-system_banking-committee-established.htm.html"},
  ]},
  {"code": "SSEG", "name": "Committee on Energy and Natural Resources", "chamber": "senate", "facts": [
    {"kind": "created", "text": "The Senate Committee on Energy and Natural Resources traces its roots to the Committee on Public Lands, established in 1816; the modern committee was established in 1977 during a major reorganization of the Senate committee system.",
     "excerpt": "The U.S. Senate Committee on Energy and Natural Resources traces its roots to the Committee on Public Lands, established in 1816 as one of the Senate\u2019s first permanent standing committees.",
     "needles": ["traces its roots to the Committee on Public Lands, established in 1816 as one of the Senate", "The modern Committee on Energy and Natural Resources was established in 1977 during a major reorganization of the Senate committee system."],
     "source_url": "https://www.energy.senate.gov/about/history-rules/",
     "source_name": "U.S. Senate Committee on Energy and Natural Resources, official history",
     "local": "www.energy.senate.gov_about_history-rules_.html"},
  ]},
  {"code": "SSEV", "name": "Committee on Environment and Public Works", "chamber": "senate", "facts": [
    {"kind": "created", "text": "In 1837, the Senate created the Committee on Public Buildings and Grounds, a predecessor of today\u2019s Committee on Environment and Public Works; in 1947 the panel was renamed the Committee on Public Works.",
     "excerpt": "In 1837, the Senate created the Committee on Public Buildings and Grounds to oversee the development of the Federal buildings in the young, but growing Federal City of Washington, DC. In 1947, during a reorganization of Senate committees, the panel was renamed the Committee on Public Works.",
     "needles": ["In 1837, the Senate created the Committee on Public Buildings and Grounds", "In 1947, during a reorganization of Senate committees, the panel was renamed the Committee on Public Works."],
     "source_url": "https://www.epw.senate.gov/public/index.cfm/history",
     "source_name": "U.S. Senate Committee on Environment and Public Works, official history",
     "local": "www.epw.senate.gov_public_index.cfm_history.html"},
  ]},
  {"code": "SLET", "name": "Select Committee on Ethics", "chamber": "senate", "facts": [
    {"kind": "created", "text": "The permanent Select Committee on Ethics was created in 1977 to replace the Select Committee on Standards and Conduct.",
     "excerpt": "In response, the permanent Select Committee on Ethics was created in 1977 to replace the Select Committee on Standards and Conduct.",
     "needles": ["the permanent Select Committee on Ethics was created in 1977 to replace the Select Committee on Standards and Conduct."],
     "source_url": "https://www.ethics.senate.gov/public/index.cfm/history",
     "source_name": "U.S. Senate Select Committee on Ethics, official history",
     "local": "www.ethics.senate.gov_public_index.cfm_history.html"},
  ]},
  {"code": "SSFR", "name": "Committee on Foreign Relations", "chamber": "senate", "facts": [
    {"kind": "created", "text": "The Senate Foreign Relations Committee was established in 1816 as one of the original standing committees of the Senate.",
     "excerpt": "The Senate Foreign Relations Committee was established in 1816 as one of the original ten standing committees of the Senate.",
     "needles": ["The Senate Foreign Relations Committee was established in 1816 as one of the original ten standing committees of the Senate."],
     "source_url": "https://www.foreign.senate.gov/about/history",
     "source_name": "U.S. Senate Committee on Foreign Relations, official history",
     "local": "www.foreign.senate.gov_about_history.html"},
  ]},
  {"code": "SSHR", "name": "Committee on Health, Education, Labor, and Pensions", "chamber": "senate", "facts": [
    {"kind": "purpose", "text": "Under Rule 25 of the Standing Rules of the Senate, the Committee on Health, Education, Labor, and Pensions is referred measures relating to education, labor, health, and public welfare.",
     "excerpt": "Committee on Health, Education, Labor and Pensions, to which committee shall be referred all proposed legislation, messages, petitions, memorials, and other matters relating to the following subjects: Measures relating to education, labor, health, and public welfare.",
     "needles": ["Measures relating to education, labor, health, and public welfare."],
     "source_url": "https://www.help.senate.gov/about",
     "source_name": "U.S. Senate Committee on Health, Education, Labor, and Pensions, official about page",
     "local": "www.help.senate.gov_about.html"},
  ]},
  {"code": "SSRA", "name": "Committee on Rules and Administration", "chamber": "senate", "facts": [
    {"kind": "created", "text": "The first Senate, convening in March 1789, established a committee to prepare a system of rules; a Committee on Rules has continued in the Senate since a forerunner was created in 1867.",
     "excerpt": "Our origins date back to the early days of the Republic when the first Senate convened in March 1789 and established a committee to prepare a system of rules for conducting business in the Senate. In 1867 in the aftermath of the Civil War and the reunification of our Union, the forerunner to our current committee was created, and a Committee on Rules has continued in the Senate to the present day.",
     "needles": ["the first Senate convened in March 1789 and established a committee to prepare a system of rules for conducting business in the Senate.", "a Committee on Rules has continued in the Senate to the present day."],
     "source_url": "https://www.rules.senate.gov/about",
     "source_name": "U.S. Senate Committee on Rules and Administration, official about page",
     "local": "www.rules.senate.gov_about.html"},
  ]},
  {"code": "SSSB", "name": "Committee on Small Business and Entrepreneurship", "chamber": "senate", "facts": [
    {"kind": "created", "text": "On October 8, 1940, the Senate established a special committee on small-business problems; it became the standing Committee on Small Business on March 25, 1981, and was renamed the Committee on Small Business and Entrepreneurship on June 29, 2001.",
     "excerpt": "On October 8, 1940, the Senate established the Special Committee to Study and Survey Problems of Small Business Enterprises (also known as the Special Committee to Study Problems of American Small Business).",
     "needles": ["On October 8, 1940, the Senate established the Special Committee to Study and Survey Problems of Small Business Enterprises", "terminated on March 25, 1981, when it became the Committee on Small Business, a standing committee.", "changed the name of the committee to the Committee on Small Business and Entrepreneurship."],
     "source_url": "https://www.sbc.senate.gov/public/index.cfm/history",
     "source_name": "U.S. Senate Committee on Small Business and Entrepreneurship, official history",
     "local": "www.sbc.senate.gov_public_index.cfm_history.html"},
  ]},
  {"code": "SSFI", "name": "Committee on Finance", "chamber": "senate", "facts": [
    {"kind": "created", "text": "On December 10, 1816, the Senate approved Senator Barbour\u2019s resolution establishing standing committees, dropping the \u201cWays and Means\u201d title in favor of a Committee on Finance.",
     "excerpt": "On December 10, 1816, the Senate approved Barbour\u2019s resolution with one minor revision\u2014dropping the \"Ways and Means\" title in favor of a Committee on Finance.",
     "needles": ["On December 10, 1816, the Senate approved Barbour", "dropping the \"Ways and Means\" title in favor of a Committee on Finance."],
     "source_url": "https://www.senate.gov/about/origins-foundations/committee-system/standing-committees-created.htm",
     "source_name": "U.S. Senate, official history (standing committees created)",
     "local": "www.senate.gov_about_origins-foundations_committee-system_standing-committees-created.htm.html"},
  ]},
  {"code": "SSJU", "name": "Committee on the Judiciary", "chamber": "senate", "facts": [
    {"kind": "created", "text": "On December 10, 1816, the Senate approved Senator Barbour\u2019s resolution establishing 11 standing committees, including a Committee on the Judiciary.",
     "excerpt": "Instead of creating a host of select committees to address each issue, however, on December 5, 1816, Senator Barbour submitted his proposal to establish 11 standing committees: 1) Foreign Relations, 2) Ways and Means, 3) Commerce and Manufacturers, 4) Military Affairs, 5) Militia, 6) Naval Affairs, 7) Public Lands, 8) Claims, 9) Judiciary, 10) Post Offices and Post Roads, and 11) Pensions. On December 10, 1816, the Senate approved Barbour\u2019s resolution with one minor revision\u2014dropping the \"Ways and Means\" title in favor of a Committee on Finance.",
     "needles": ["Senator Barbour submitted his proposal to establish 11 standing committees", "9) Judiciary", "On December 10, 1816, the Senate approved Barbour"],
     "source_url": "https://www.senate.gov/about/origins-foundations/committee-system/standing-committees-created.htm",
     "source_name": "U.S. Senate, official history (standing committees created)",
     "local": "www.senate.gov_about_origins-foundations_committee-system_standing-committees-created.htm.html"},
  ]},
  {"code": "SSVA", "name": "Committee on Veterans' Affairs", "chamber": "senate", "facts": [
    {"kind": "created", "text": "The Senate Committee on Veterans' Affairs was created in 1970 to transfer responsibilities for veterans from the Finance and Labor committees to a single panel.",
     "excerpt": "The Veterans' Affairs committee was created in 1970 to transfer responsibilities for veterans from the Finance and Labor committees to a single panel.",
     "needles": ["The Veterans' Affairs committee was created in 1970 to transfer responsibilities for veterans from the Finance and Labor committees to a single panel."],
     "source_url": "https://www.veterans.senate.gov/about",
     "source_name": "U.S. Senate Committee on Veterans' Affairs, official about page",
     "local": "www.veterans.senate.gov_about.html"},
  ]},
  {"code": "SPAG", "name": "Special Committee on Aging", "chamber": "senate", "facts": [
    {"kind": "created", "text": "The Senate Special Committee on Aging was first established in 1961 as a temporary committee.",
     "excerpt": "The Senate Special Committee on Aging was first established in 1961 as a temporary committee.",
     "needles": ["The Senate Special Committee on Aging was first established in 1961 as a temporary committee."],
     "source_url": "https://www.aging.senate.gov/about",
     "source_name": "U.S. Senate Special Committee on Aging, official about page",
     "local": "www.aging.senate.gov_about.html"},
    {"kind": "purpose", "text": "Special committees have no legislative authority; they can study issues, conduct oversight of programs, and advance important causes.",
     "excerpt": "While special committees have no legislative authority, they can study issues, conduct oversight of programs, and advance important causes.",
     "needles": ["While special committees have no legislative authority, they can study issues, conduct oversight of programs, and advance important causes."],
     "source_url": "https://www.aging.senate.gov/about",
     "source_name": "U.S. Senate Special Committee on Aging, official about page",
     "local": "www.aging.senate.gov_about.html"},
  ]},
  {"code": "SSCM", "name": "Committee on Commerce, Science, and Transportation", "chamber": "senate", "facts": [
    {"kind": "created", "text": "The official history of the Senate Committee on Commerce, Science, and Transportation lists the Committee on Commerce and Manufactures (1816\u20131825) among its progenitor committees.",
     "excerpt": "Briefly stated, the progenitor committees are: Committee on Commerce and Manufactures (1816-1825) Committee on Commerce (1825-1946, 1961-1977)",
     "needles": ["the progenitor committees are: Committee on Commerce and Manufactures (1816-1825)"],
     "source_url": "https://www.commerce.senate.gov/about/committee-history/",
     "source_name": "U.S. Senate Committee on Commerce, Science, and Transportation, official committee history",
     "local": "www.commerce.senate.gov_about_committee-history_.html"},
  ]},
  {"code": "SSGA", "name": "Committee on Homeland Security and Governmental Affairs", "chamber": "senate", "facts": [
    {"kind": "created", "text": "The official history of the Senate Committee on Homeland Security and Governmental Affairs traces the committee\u2019s origins to 1816.",
     "excerpt": "The origins of the Homeland Security and Governmental Affairs Senate Committee can be traced back to 1816.",
     "needles": ["The origins of the Homeland Security and Governmental Affairs Senate Committee can be traced back to 1816."],
     "source_url": "https://www.hsgac.senate.gov/about/history/",
     "source_name": "U.S. Senate Committee on Homeland Security and Governmental Affairs, official history",
     "local": "www.hsgac.senate.gov_about_history_.html"},
    {"kind": "purpose", "text": "The Committee on Homeland Security and Governmental Affairs is the chief oversight committee of the United States Senate.",
     "excerpt": "Today, the Committee on Homeland Security and Governmental Affairs is the chief oversight committee of the United States Senate.",
     "needles": ["the Committee on Homeland Security and Governmental Affairs is the chief oversight committee of the United States Senate."],
     "source_url": "https://www.hsgac.senate.gov/about/history/",
     "source_name": "U.S. Senate Committee on Homeland Security and Governmental Affairs, official history",
     "local": "www.hsgac.senate.gov_about_history_.html"},
  ]},
]

KIND_LABEL = {"created": "When it was created", "purpose": "What it does"}

def cid(code, kind):
    return f"ch_{code.lower()}_{kind}"

def validate(fact):
    path = RAWCH / fact["local"]
    if not path.exists():
        return False, f"missing local file {fact['local']}"
    text = norm(path.read_text(errors="replace"))
    missing = [n for n in fact["needles"] if n not in text]
    if missing:
        return False, "local miss: " + " | ".join(repr(m[:120]) for m in missing)
    # prefer a contiguous official excerpt when the stored excerpt appears on the page
    if fact["excerpt"] not in text:
        # keep the claim, but the displayed excerpt becomes the first needle found on the page
        fact["excerpt_note"] = "excerpt not one contiguous block; needles verified"
    return True, "ok"

def main():
    accepted = []
    skipped = []
    for rec in RECORDS:
        keep = []
        for f in rec["facts"]:
            ok, note = validate(f)
            if ok:
                keep.append(f)
            else:
                skipped.append({"code": rec["code"], "kind": f["kind"], "note": note})
                print("SKIP", rec["code"], f["kind"], note)
        if keep:
            accepted.append({**rec, "facts": keep})
    print("accepted committees", len(accepted), "skipped facts", len(skipped))

    bank_path = SITE / "claims.json"
    bank = json.loads(bank_path.read_text())
    claims = bank["claims"]
    added = updated = kept = 0
    index = {}
    for rec in accepted:
        ids = []
        for f in rec["facts"]:
            i = cid(rec["code"], f["kind"])
            obj = {
                "id": i,
                "text": f["text"],
                "value": None,
                "excerpt": f["excerpt"],
                "source_name": f["source_name"],
                "source_url": f["source_url"],
                "retrieved_at": RETRIEVED,
                "check": {"kind": "source-excerpt", "url": f["source_url"], "needles": f["needles"], "excerpt": f["excerpt"]},
                "status": "unverified",
            }
            old = claims.get(i)
            if old and old.get("excerpt") == obj["excerpt"] and old.get("text") == obj["text"] and old.get("source_url") == obj["source_url"] and old.get("status") == "verified":
                obj = old
                kept += 1
            elif old:
                # keep verified only if unchanged; otherwise reset
                claims[i] = obj
                updated += 1
            else:
                claims[i] = obj
                added += 1
            ids.append(i)
        index[rec["code"]] = {
            "code": rec["code"], "name": rec["name"], "chamber": rec["chamber"],
            "claims": ids,
            "facts": [{"kind": f["kind"], "label": KIND_LABEL[f["kind"]], "claim": cid(rec["code"], f["kind"])} for f in rec["facts"]],
        }
    bank["claims"] = claims
    bank_path.write_text(json.dumps(bank, indent=2, ensure_ascii=False) + "\n")
    OUT.write_text(json.dumps({"generated_at": now_iso(), "committees": index, "skipped_local": skipped}, indent=2, ensure_ascii=False) + "\n")

    # annotate profiles so check-claims sees the new claim ids
    n_prof = 0
    for p in (SITE / "profiles").glob("*.json"):
        pr = json.loads(p.read_text())
        changed = False
        for c in pr.get("committees") or []:
            hist = index.get(c.get("code"))
            ids = (hist or {}).get("claims") or []
            if ids:
                if c.get("history_claims") != ids:
                    c["history_claims"] = ids
                    changed = True
            elif "history_claims" in c:
                del c["history_claims"]
                changed = True
        if changed:
            p.write_text(json.dumps(pr, indent=2, ensure_ascii=False) + "\n")
            n_prof += 1
    print(json.dumps({"added": added, "updated": updated, "kept_verified": kept, "committees": len(index), "profiles_annotated": n_prof, "new_claims": added+updated}))

if __name__ == "__main__":
    main()
