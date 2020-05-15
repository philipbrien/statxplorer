# statxplorer
 Python interface to the UK Government Department for Work and Pensions'
 [Stat-Xplore](https://stat-xplore.dwp.gov.uk/) data service.

This is largely a Python re-implementation of Oli Hawkins' 
[statxplorer](https://github.com/olihawkins/statxplorer) package for R. The 
interface is similar (although modified to make it more Pythonic) and it
returns data in Pandas dataframes, the closest equivalent to R dataframes.

## Installation
You can use `pip` to install `statxplorer` directly from GitHub:

```
pip install https://github.com/philipbrien/statxplorer/zipball/master
```

Alternatively, download the statxplorer.py file and place it in the same 
directory as the module you wish to call it from, or somewhere else in your 
PYTHONPATH.

### Prerequisites
`statxplorer` uses Python 3. You will also need the `pandas` module 
installed, because all data is returned in the form of a Pandas dataframe, and
`requests` for accessing the API. If you install using `pip`, these should be
installed automatically.

## Authentication
You will need a Stat-Xplore key to access the API. You can get this by 
[registering for an account](https://stat-xplore.dwp.gov.uk/webapi/jsf/user/register.xhtml)
on the Stat-Xplore website; you can then get your key by logging in, clicking
the three-dot menu in the top right, and clicking "Account". The key is
listed under "Open Data API Access".

## How to use statxplorer
Store your access key as a string, then use it to create an instance of the 
`StatXplorer` class, like this:

```python
import statxplorer

key = "your_statxplore_key_here"

explorer = statxplorer.StatXplorer(key)
```

You can then get data using the `fetch_table` method. This takes a Stat-Xplore
JSON query, which are complex - the easiest way to do this is to generate the
query using the Stat-Xplore web interface. `fetch_table` accepts a Python 
representation of the query, a file object referring to a JSON file, or the 
path to a JSON file:

```python
import json

query_file = open("table_2020-01-01_12-00-00.json")

# Any of these will work:
query = query_file
query = json.load(query_file)
query = "table_2020-01-01_12-00-00.json"

results = explorer.fetch_table(query)
```

This returns the full JSON object from the Stat-Xplore API, [as defined here](https://stat-xplore.dwp.gov.uk/webapi/online-help/Open-Data-API-Table.html).
Additionally, a Pandas `DataFrame` holding the results can be found in 
`results["data"]`. For debugging purposes, the raw response from the API 
including HTTP headers is stored as a `requests` Request object under 
`results["req"]`.

### Reshaping the data
`statxplorer` tries to carry out the most sensible manipulation of the data
that it can. By default, it will pivot the data so that the first field
specified is used as the rows, the second is used for columns, and all other
fields are added as extra rows.

If your data is laid out in a more complex way than this, or uses custom
field definitions, the results may not be as you expected. If this is the case,
use the `reshape=False` argument to return the data just as it comes from the 
API - you can then do your own reshaping with Pandas.

```python
results = explorer.fetch_table(query, reshape=False)
```

### Geographical codes
For some geographical fields, Stat-Xplore returns ONS codes that can be useful
for identifying specific geographical areas. `statxplorer` can extract these
from the data and add them as an extra column - just set `include_codes` to
`True`.

```python
results = explorer.fetch_table(query, include_codes=True)
```

## Troubleshooting
`statxplorer` includes a few custom exceptions:
* `AuthenticationError`: this is raised if your Stat-Xplore key is not valid.
 Check that you copied it correctly and stored it as a string.
* `RequestFailedError`: this indicates that your query wasn't valid. Query 
 objects are complex and easy to get wrong, so take care if you edit them
 yourself.
* `ServiceUnavailableError`: the Stat-Xplore API is down. The Stat-Xplore API 
can be a bit unreliable. `statxplorer` tries its best to
cope with this by retrying connections if they initially fail, but if the
API is down completely this error will be raised. Check the website and try
again later.
