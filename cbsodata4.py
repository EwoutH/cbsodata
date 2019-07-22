# Copyright (c) 2019 Jonathan de Bruin

#  Permission is hereby granted, free of charge, to any person
#  obtaining a copy of this software and associated documentation
#  files (the "Software"), to deal in the Software without
#  restriction, including without limitation the rights to use,
#  copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the
#  Software is furnished to do so, subject to the following
#  conditions:

#  The above copyright notice and this permission notice shall be
#  included in all copies or substantial portions of the Software.

#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
#  OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
#  NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
#  HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
#  WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
#  OTHER DEALINGS IN THE SOFTWARE.

"""Statistics Netherlands opendata version 4 API client for Python"""

__all__ = [
    'options',
    'get_data',
    'get_dataset',
    'get_dataset_info',
    'get_dataset_list',
    'get_catalog_info',
    'get_catalog_list',
    'get_metadata',
    'get_observations']

import copy
import json
import logging
import os
import re
from contextlib import contextmanager

import requests
from requests import Session, Request


class OptionsManager(object):
    """Class for option management"""

    def __init__(self):

        # url of cbs odata4 service
        self.odata_url = "http://beta.opendata.cbs.nl/OData4"
        self.catalog = "CBS"
        self.odata_version = "4"

        # Enable in next version
        # self.catalog_url = "opendata.cbs.nl"

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return "odata_url = {}, catalog = {}, odata_version = {}".format(
            self.odata_url, self.catalog, self.api_version)

    def __getitem__(self, arg):
        return getattr(self, arg)

    def __setitem__(self, arg, value):
        setattr(self, arg, value)

    def _log_setting_change(self, setting_name, old_value, new_value):
        logging.info(
            "Setting '{}' changed from '{}' to '{}'.".format(
                setting_name, old_value, new_value)
        )

    def __getattr__(self, arg):
        return getattr(self, arg)

    def __setattr__(self, arg, value):
        try:
            old_value = copy.copy(getattr(self, arg))
        except Exception:
            old_value = "undefined"

        self._log_setting_change(arg, old_value, value)
        super(OptionsManager, self).__setattr__(arg, value)


# User options
options = OptionsManager()


def _odata4_request(url, kind="EntitySet", params={}):

    try:

        s = Session()
        p = Request('GET', url, params=params).prepare()

        logging.info("Download " + p.url)

        r = s.send(p)
        r.raise_for_status()

    except requests.HTTPError as http_err:
        http_err.message = "Downloading metadata '{}' failed. {}".format(
            p.url, str(http_err)
        )

        raise http_err

    res = r.json(encoding='utf-8')

    # check the data context
    if kind == "Singleton":
        del res["@odata.context"]
        return res
    elif kind == "EntitySet":
        data = copy.copy(res['value'])

        if "@odata.nextLink" in res.keys():
            data_next = _odata4_request(
                res['@odata.nextLink'],
                kind=kind,
                params=params
            )
            data.extend(data_next)

        return data
    else:
        raise ValueError("Unknown kind '{}'.".format(kind))


def _filter(filter):
    """Filter rows with a CBS-style query.

    Parameters
    ----------
    filter : str
        The rows to return.

    Returns
    -------
    str
        Filter parameter for URL
    """

    return filter


def _save_data(data, dir, metadata_name):
    """Save the data."""

    if not os.path.exists(dir):
        os.makedirs(dir)

    fp = os.path.join(dir, metadata_name + '.json')

    with open(fp, 'w') as output_file:
        json.dump(data, output_file, indent=2)


def _read_data(*args, **kwargs):
    pass


def download_data(table_id, catalog=None):

    raise NotImplementedError


def get_metadata(dataset_id, catalog=None):
    """Get the metadata of the dataset.

    Parameters
    ----------
    dataset_id : str
        The identifier of the dataset. Find the identifier in the list
        of datasets with get_dataset_list() or navigate to
        https://beta.opendata.cbs.nl/OData4/index.html.
    catalog : str
        The name of the catalog. Default options.catalog. Get a list
        of catalogs with get_catalog_list() or navigate to
        https://beta.opendata.cbs.nl/OData4/index.html.

    Returns
    -------
    list
        A dictionary with the (meta)data of the table
    """

    catalog = options.catalog if catalog is None else catalog

    dataset_url = "{}/{}/{}/".format(options.odata_url, catalog, dataset_id)
    dataset_odata_meta_list = _odata4_request(dataset_url)

    # https://beta.opendata.cbs.nl/OData4/CBS/83765NED/

    metadata = {}

    for metadata_object in dataset_odata_meta_list:

        if metadata_object['name'].endswith("Groups") or \
                metadata_object['name'].endswith("Codes") or \
                metadata_object['name'] == "Dimensions" or \
                metadata_object['name'] == "Properties":

            metadata_url = dataset_url + metadata_object['url']
            metadata_table = _odata4_request(
                metadata_url,
                kind=metadata_object['kind']
            )
            metadata[metadata_object['name']] = metadata_table

    return metadata


def get_observations(table_id, catalog=None, filter=None,
                     top=None, skip=None):
    """Get the observation of the dataset.

    Parameters
    ----------
    dataset_id : str
        The identifier of the dataset. Find the identifier in the list
        of datasets with get_dataset_list() or navigate to
        https://beta.opendata.cbs.nl/OData4/index.html.
    catalog : str
        The name of the catalog. Default options.catalog. Get a list
        of catalogs with get_catalog_list() or navigate to
        https://beta.opendata.cbs.nl/OData4/index.html.
    filter : str
        Return only rows that agree on the filter.
    top : int
        Return the top x observations. Default returns all.
    skip : int
        Skip the top x observations. Default 0.

    Returns
    -------
    list
        A dictionary with the observations.
    """
    catalog = options.catalog if catalog is None else catalog

    observations_url = "{}/{}/{}/Observations".format(
        options.odata_url,
        catalog,
        table_id
    )
    payload = {"$filter": filter} if filter else {}

    if top is not None:
        payload["$top"] = top
    if skip is not None:
        payload["$skip"] = skip

    return _odata4_request(
        observations_url,
        kind="EntitySet",
        params=payload
    )


def get_data(dataset_id,
             catalog=None,
             filter=None,
             measure_vars=["Title", "Unit"],
             include_measure_code_id=True,
             measure_group_vars=["Title"],
             include_measure_group_id=True,
             dimension_vars=["Title"],
             include_dimension_code_id=True,
             dimension_group_vars=["Title"],
             include_dimension_group_id=False,
             top=None,
             skip=None):
    """Get the enriched observation of the dataset.

    Parameters
    ----------
    dataset_id : str
        The identifier of the dataset. Find the identifier in the list
        of datasets with get_dataset_list() or navigate to
        https://beta.opendata.cbs.nl/OData4/index.html.
    catalog : str
        The name of the catalog. Default options.catalog. Get a list
        of catalogs with get_catalog_list() or navigate to
        https://beta.opendata.cbs.nl/OData4/index.html.
    filter : str
        Filter observations. See
        https://beta.opendata.cbs.nl/OData4/implement.html for filter.
        At the moment, it is only possible to filter on observations.
    measure_vars : list
        A list of labels and variables to include for each measure
        code. Examples are "Title", "Description", "DataType",
        "Unit", "Format","Decimals","PresentationType".
        Default ["Title", "Unit"]
    measure_group_vars : list
        A list of labels and variables to include for each measure
        group. Examples are "Title", "Description" and "ParentID"
        Default ["Title"]
    include_measure_group_id : bool
        Include the Identifier of the Measure Group. Default True.
    dimension_vars : list
        A list of labels and variables to include for each dimension
        code. Examples are "Title", "Description", "DataType",
        "Unit", "Format","Decimals","PresentationType".
        Default ["Title", "Unit"]
    dimension_group_vars : list
        A list of labels and variables to include for each dimension
        group. Examples are "Title", "Description" and "ParentID"
        Default ["Title"]
    include_dimension_group_id : bool
        Include the Identifier of the Dimension Group. Default False.
        (The default of this option is False because the Group ID
        has no added value.)
    top : int
        Return the top x observations. Default returns all.
    skip : int
        Skip the top x observations. Default 0.

    Returns
    -------
    list
        A dictionary with the enriched observations.
    """

    observations = get_observations(
        dataset_id,
        catalog,
        filter=filter,
        top=top,
        skip=skip
    )

    # add codes
    meta = get_metadata(dataset_id,
                        catalog=catalog)

    def _lookup_dict(d, meta, key, drop_key=True):
        r = dict(d, **meta.get(d[key], {}))
        if drop_key:
            del r[key]
        return r

    if measure_vars or measure_group_vars:

        # transform measure codes into key-value pairs
        code_meas_meta_dict = {}
        for d in meta["MeasureCodes"]:  # loop over all meta records

            # include all measure_vars with the name "Measure"
            # as a prefix
            temp_meas_dict = {
                "Measure" + k: d[k] for k in measure_vars
            }

            # if there are group variables to include, we need the
            # MeasureGroupID.
            if measure_group_vars:
                temp_meas_dict["MeasureGroupID"] = d["MeasureGroupID"]

            # update the dict
            code_meas_meta_dict[d["Identifier"]] = temp_meas_dict

        observations = [
            _lookup_dict(d, code_meas_meta_dict, "Measure",
                         drop_key=not include_measure_code_id)
            for d in observations
        ]

        # measure groups
        if "MeasureGroups" in meta.keys() and measure_group_vars:
            group_meta_dict = {
                d["ID"]: {"MeasureGroup" + k: d[k] for k in measure_group_vars}
                for d in meta["MeasureGroups"]}
            observations = [
                _lookup_dict(
                    d,
                    group_meta_dict,
                    "MeasureGroupID",
                    drop_key=not include_measure_group_id
                )
                for d in observations]

    # dimension codes
    if dimension_vars or dimension_group_vars:

        # get a list of the dimension names
        dimensions = [dim["Identifier"] for dim in meta['Dimensions']]

        # add code and group info for each dimension
        for dim in dimensions:

            # transform codes into key-value pairs
            code_dim_meta_dict = {}
            for d in meta[dim + "Codes"]:  # loop over all meta records

                # include all dimension_vars with the name of the dimension
                # as a prefix
                temp_dim_dict = {
                    dim + k: d[k] for k in dimension_vars
                }

                # if there are group variables to include, we need the GroupID.
                if dimension_group_vars:
                    temp_dim_dict[dim + "GroupID"] = d["DimensionGroupID"]

                code_dim_meta_dict[d["Identifier"]] = temp_dim_dict

            # Update the observations
            observations = [
                _lookup_dict(d, code_dim_meta_dict, key=dim,
                             drop_key=not include_dimension_code_id)
                for d in observations
            ]

            # append dimension group vars.
            if dimension_group_vars:

                # groups
                meta_group_name = dim + "Groups"

                if meta_group_name in meta.keys():
                    group_meta_dict = {
                        d["ID"]: {
                            dim + "Group" + k: d[k]
                            for k in dimension_group_vars
                        }
                        for d in meta[meta_group_name]}
                    observations = [
                        _lookup_dict(
                            d,
                            group_meta_dict,
                            dim + "GroupID",
                            drop_key=not include_dimension_group_id
                        )
                        for d in observations
                    ]

    return observations


def get_dataset(*args, **kwargs):
    return get_data(*args, **kwargs)


def get_catalog_list():
    """Get a list with the available catalogs.

    Returns
    -------
    list
        A list with the description of catalogs."""

    catalog_url = "{}/Catalogs".format(
        options.odata_url
    )
    return _odata4_request(catalog_url)


def get_catalog_info(catalog):
    """Get information on the catalog.

    Parameters
    ----------
    catalog : str
        The name of the catalog. Default ``options.catalog``. Get a
        list of the available catalogs with get_catalog_list() or
        navigate to https://beta.opendata.cbs.nl/OData4/index.html.

    Returns
    -------
    dict
        A dictionary with the description of the catalog.
    """

    try:
        catalog_url = "{}/Catalogs/{}".format(
            options.odata_url,
            catalog
        )

        return _odata4_request(catalog_url, kind="Singleton")

    except requests.HTTPError as err:

        # check if catalog is a dataset to get more informative error
        pattern = re.compile(r"\d{5,6}[A-Z]{3}")
        catalog_is_dataset = pattern.match(catalog)

        if catalog_is_dataset:
            raise ValueError(
                "Catalog '{}' seems to be a dataset identifier.".format(
                    catalog
                )
            )
        elif err.response.status_code == 404:
            raise ValueError(
                "Catalog '{}' not found.".format(
                    catalog
                )
            )
        else:
            raise err


def get_dataset_list(catalog=None):
    """Get a list with the available datasets.

    Parameters
    ----------
    catalog : str
        The name of the catalog. Default None. Get a
        list of the available catalogs with get_catalog_list() or
        navigate to https://beta.opendata.cbs.nl/OData4/index.html.

    Returns
    -------
    list
        A list with the description of datasets.
    """

    catalog = "" if catalog is None else catalog
    catalog_url = "{}/{}/Datasets".format(
        options.odata_url,
        catalog
    )
    return _odata4_request(catalog_url)


def get_dataset_info(dataset_id, catalog=None):
    """Get information on the dataset.

    Parameters
    ----------
    dataset_id : str
        The identifier of the dataset. Find the identifier in the list
        of datasets with get_dataset_list() or navigate to
        https://beta.opendata.cbs.nl/OData4/index.html.
    catalog : str
        The name of the catalog. Default ``options.catalog``. Get a
        list of the available catalogs with get_catalog_list() or
        navigate to https://beta.opendata.cbs.nl/OData4/index.html.

    Returns
    -------
    dict
        A dictionary with the description of the dataset.
    """

    catalog = options.catalog if catalog is None else catalog

    url = "{}/{}/{}/Properties".format(
        options.odata_url,
        catalog,
        dataset_id
    )

    return _odata4_request(url, kind="Singleton")


@contextmanager
def catalog(catalog):
    """Context manager for catalogs.

    Parameters
    ----------
    catalog : str
        The catalog. For example: 'CBS' or 'CBS-Maatwerk'.

    """

    old = copy.copy(options.catalog)
    options.catalog = catalog

    yield

    options.catalog = old