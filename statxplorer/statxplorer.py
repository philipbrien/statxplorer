# -*- coding: utf-8 -*-
"""
StatXplorer - Python interface to the Department for Work and Pensions'
Stat-Xplore statistical service
"""

# Standard library imports
import json
import time
from collections import OrderedDict

# Required third-party imports
import requests
import pandas as pd

# Constants
STATXPLORE_BASE_URL = "https://stat-xplore.dwp.gov.uk/webapi/rest/v1"
ENDPOINTS = ["schema", "table", "info", "rate_limit"]
MAX_RETRIES = 5 # Maximum times to try to connect to Stat-Xplore

# Exceptions
class AuthenticationError(RuntimeError):
    """Exception indicating that authentication to Stat-Xplore failed."""
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

class RequestFailedError(RuntimeError):
    """Exception indicating that a Stat-Xplore query failed to return anything
    useful."""
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        
class ServiceUnavailableError(ConnectionError):
    """Exception indicating that Stat-Xplore is down."""
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)


# Recursive generators
def field_looper(field_names, field_labels):
    """Generator that returns each combination of fields in turn.  For each one
    it returns an ordered dict of field name: field label."""
    
    # We're going through these lists together, so they must be the same 
    # length.
    assert len(field_names) == len(field_labels)
    
    if len(field_names) == 1:
        # Looking at the bottom level.  Just loop through the labels.
        for label in field_labels[0]:
            yield OrderedDict({field_names[0]: label})
    else:
        # We're above the bottom level so we'll be calling ourselves again.
        # Loop over the first list of labels.
        for label in field_labels[0]:
            for lower_output in field_looper(field_names[1:], 
                                             field_labels[1:]):
                output = OrderedDict({field_names[0]: label})
                output.update(lower_output)
                yield output

        
def value_looper(array):
    """Generator that returns each element of a multi-dimensional array in
    turn, depth-first."""
    if isinstance(array[0], list):
        # There's another list inside this one - recurse again.
        for internal_array in array:
            for item in value_looper(internal_array):
                yield item
    else:
        # Not a list, so we're at the bottom.  Just yield each item in this
        # array.
        for item in array:
            yield item


# Main class
class StatXplorer(object):
    """Main interface for accessing Stat-Xplore."""
    def __init__(self, key):
        """Constructor.  Validate and save off the Stat-Xplore private key."""
        self.key = key
        
        # Do a simple sense check to make sure that this key works.
        req = self.request("info")
        if req.status_code != 200:
            raise AuthenticationError("Login to Stat-Xplore failed.  Check "
                                      "that the key supplied is correct.")

    def request(self, endpoint, payload=None):
        """Make an authenticated request to the Stat-Xplore API, and return 
        the requests object."""
        if endpoint not in ENDPOINTS:
            raise ValueError("Unrecognised endpoint: {0}".format(endpoint))
        
        url = STATXPLORE_BASE_URL + "/" + endpoint
        retries = 0
        while retries < MAX_RETRIES:
            if endpoint == "table":
                req = requests.post(url,
                                    headers={"APIKey": self.key},
                                    json=payload)
            else:
                req = requests.get(url, headers={"APIKey": self.key})
                
            if req.status_code == 503:
                # Service down.  This usually means it's down for maintenance.
                raise ServiceUnavailableError("Stat-Xplore is unavailable.  "
                                              "It may be down for maintenance"
                                              " - check the website at "
                                              "https://stat-xplore.dwp."
                                              "gov.uk/.")
            elif req.status_code == 504:
                # Gateway timeout.  This happens occasionally - wait a moment 
                # and try again.
                time.sleep(0.5)
            else:
                break
            retries += 1
        
        if retries == MAX_RETRIES:
            raise TimeoutError("Stat-Xplore connection timed out.  "
                               "Wait a few minutes and try again.")
            
        return req
    
    def convert_to_dataframe(self, results, include_codes, reshape):
        """Convert the results returned from Stat-Xplore into a dataframe."""
        # First generate an ordered list of all the fields we will
        # be using, in human-readable format.
        field_names = [f["label"] for f in results["fields"]]
        
        # Next generate lists of all the values for each field, so that they
        # match up with the order of the data.
        field_labels = []
        for field in results["fields"]:
            field_labels.append([f["labels"][0] for f in field["items"]])
            
        if include_codes:
            # Certain fields include ONS codes in their URIs.  We should be
            # able to find these because ONS codes are always exactly 9
            # characters long and begin with a letter.
            field_codes = {}
            for field in results["fields"]:
                for item in field["items"]:
                    if "uris" not in item:
                        # This field label doesn't have a URI associated with
                        # it (might be a Totals row), so ignore it.
                        continue
                    code = item["uris"][0].rsplit(":", maxsplit=1)[1]
                    if len(code) == 9 and code[0].isalpha():
                        if field["label"] not in field_codes:
                            field_codes[field["label"]] = {}
                        field_codes[field["label"]][item["labels"][0]] = code
            
        # Now go through all the measures and all the results in turn, saving
        # them off into a flat list.
        data = []
        for measure in results["measures"]:
            result_cube = results["cubes"][measure["uri"]]
            for field_row, value in zip(field_looper(field_names, 
                                                     field_labels), 
                                        value_looper(result_cube["values"])):
                output_row = OrderedDict()
                output_row.update(field_row)
                output_row.update({measure["label"]: value})
                data.append(output_row)
                
        data_pd = pd.DataFrame(data)
        
        if not reshape:
            # We haven't been asked to reshape the data appropriately, so just
            # return the raw dataframe.
            return data_pd
    
        # The shape of the dataframe we return is based on the number of
        # fields in the query.
        if len(field_names) == 1:
            # One field is effectively flat data, so just re-index on the 
            # field and return it.
            return data_pd.set_index(field_names[0])
        else:
            # Pivot the data to flatten it down to a 2D array.  We assume that
            # the first field in the query is the first dimension, the second
            # field is the second dimension, and all other fields should be
            # stacked under the first dimension to create multi-level rows.
            # All values get passed in at once - if there is more than one
            # this will create multi-level columns.
            indices = [field_names[0]]
            if len(field_names) > 2:
                indices.extend(field_names[2:])
            columns = [field_names[1]]
            
            # Extract the column labels in their original order, as the pivot
            # operation will sort them.
            column_labels = data_pd[field_names[1]].unique()
            
            values = [m["label"] for m in results["measures"]]
            if len(values) == 1:
                values = values[0]
            data_pd = pd.pivot_table(data_pd,
                                     values=values,
                                     index=indices,
                                     columns=columns)
            
            # Put the columns back in their original order.
            data_pd = data_pd[column_labels]
            
            if include_codes:
                for field_name, code_lookup in field_codes.items():
                    if len(data_pd.index.names) == 1:
                        # Single-level index.  This means we can just do a
                        # lookup on the index values.
                        data_pd[field_name + " code"] = data_pd.index.map(
                            code_lookup)
                    else:
                        # Multi-level index.  Find the field we're looking for
                        # in the indices.
                        field_ix = data_pd.index.names.index(field_name)
                        lookup = {}
                        for values in data_pd.index.values:
                            if values[field_ix] not in code_lookup:
                                # This is an index value without a code - 
                                # possibly a Totals row.  Skip it.
                                continue
                            lookup[values] = code_lookup[values[field_ix]]
                        data_pd[field_name + " code"] = data_pd.index.map(
                            lookup)
                    data_pd = data_pd.set_index(field_name + " code", 
                                                append=True)
            
            return data_pd
            
    
    def fetch_table(self, query, include_codes=False, reshape=True):
        """Get a table from Stat-Xplore.  The best way to use this is with a
        pre-generated JSON query - this method accepts a Python dict 
        representing the query, a file-like object holding it, or a filename 
        pointing to the query file.
        
        Returns the full JSON object returned by Stat-Xplore, with an extra
        top-level element ("data") containing the results as a Pandas 
        dataframe, and another ("req") containing the Python requests object, 
        for debugging.
        
        Results with more than two dimensions will be flattened down to two.
        
        Setting "include_codes" to True will add an extra column for each field
        that uses ONS codes in its Stat-Xplore URI.
        
        Setting "reshape" to False will return a flat dataframe with no
        reshaping.  Use this and do your own reshaping if the default returns
        something weird.
        """
            
        if isinstance(query, dict):
            payload = query
        elif isinstance(query, str):
            with open(query) as queryfile:
                payload = json.load(queryfile)
        else:
            payload = query.read().strip()
            
        req = self.request("table", payload)
        if req.status_code != 200:
            raise RequestFailedError("Query failed - check that it is valid.")
            
        results = req.json()
        results["data"] = self.convert_to_dataframe(results, 
                                                    include_codes, 
                                                    reshape)
        results["req"] = req
        
        return results







