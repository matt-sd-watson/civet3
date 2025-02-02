import json
import csv
from mako.template import Template
from mako.lookup import TemplateLookup
import datetime as dt
from datetime import date
import collections
from civet import __version__
from civet.report_functions import timeline_functions
from civet.report_functions import map_functions
from civet.utils.log_colours import green,cyan

from mako.template import Template
from mako.runtime import Context
from mako.exceptions import RichTraceback
from io import StringIO
import os

from civet.utils.config import *

def make_query_summary_data(metadata, config):
    query_summary_data = []
    with open(metadata, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row[KEY_QUERY_BOOLEAN] == "True":
                table_row = {}
                for col in config[KEY_QUERY_TABLE_CONTENT]:

                    table_row[col] = row[col]
                    
                query_summary_data.append(table_row)
    
    return query_summary_data

def make_fasta_summary_data(metadata,config):

    fasta_summary_pass = []
    fasta_summary_fail = []
    with open(metadata, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["source"] == "input_fasta":
                table_row = {}

                for col in config[KEY_FASTA_TABLE_CONTENT]:
                    table_row[col] = row[col]
                if row["qc_status"] == "Pass":
                    fasta_summary_pass.append(table_row)
                else:
                    fasta_summary_fail.append(table_row)
    
    return fasta_summary_pass,fasta_summary_fail

def check_earliest_latest_dates(d,catchment_summary_dict,catchment):
    if d < catchment_summary_dict[catchment]["earliest_date"]:
        catchment_summary_dict[catchment]["earliest_date"] = d

    if d > catchment_summary_dict[catchment]["latest_date"]:
        catchment_summary_dict[catchment]["latest_date"] = d
    
def get_top_10_str(total,counter_dict):
    summary = ""
    top = counter_dict.most_common(10)
    remainder_pcent = 100
    for i in top:
        pcent = int(100*(i[1]/total))
        if pcent >= 1:
            remainder_pcent-=pcent
            summary += f"{i[0]} {pcent}% <br>"
    summary += f"Other {remainder_pcent}% <br>"
    return summary

def make_catchment_summary_data(metadata,catchments,config):
    catchment_summary_dict = {}

    for catchment in catchments:
        catchment_summary_dict[catchment] = {
            'total':0,
            'query_count':0
        }

    with open(metadata,"r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            catchment = row[KEY_CATCHMENT]

            if row[KEY_QUERY_BOOLEAN] == "True":
                catchment_summary_dict[catchment]["query_count"] +=1
            elif row[KEY_QUERY_BOOLEAN] == "False":
                catchment = row[KEY_CATCHMENT]

                catchment_summary_dict[catchment]['total'] +=1

                if config[KEY_BACKGROUND_DATE_COLUMN] in reader.fieldnames:
                    d = date.fromisoformat(row[config[KEY_BACKGROUND_DATE_COLUMN]])

                    for i in ['earliest_date','latest_date']:
                        if i not in catchment_summary_dict[catchment]:
                            catchment_summary_dict[catchment][i] = d

                    check_earliest_latest_dates(d,catchment_summary_dict,catchment)

                if config["background_location_column"] in reader.fieldnames:
                    location_column = config["background_location_column"]
                    if location_column not in catchment_summary_dict[catchment]:
                        catchment_summary_dict[catchment][location_column] = collections.Counter()
                    if row[location_column] == "":
                        catchment_summary_dict[catchment][location_column]["Unknown"]+=1
                    else:
                        catchment_summary_dict[catchment][location_column][row[location_column]]+=1
                
                if "lineage" in reader.fieldnames:
                    if "lineage" not in catchment_summary_dict[catchment]:
                        catchment_summary_dict[catchment]["lineage"] = collections.Counter()
                    
                    catchment_summary_dict[catchment]["lineage"][row['lineage']]+=1

                if "SNPs" in reader.fieldnames:
                    if "SNPs" not in catchment_summary_dict[catchment]:
                        catchment_summary_dict[catchment]["SNPs"] = collections.defaultdict(list)
                    catchment_summary_dict[catchment]["SNPs"].append(row["SNPs"])

    for catchment in catchment_summary_dict:
        total = catchment_summary_dict[catchment]["total"]
        location_column = config["background_location_column"]
        if location_column in catchment_summary_dict[catchment]:
            catchment_summary_dict[catchment][location_column] = get_top_10_str(total,catchment_summary_dict[catchment][location_column])
        if "lineage" in catchment_summary_dict[catchment]:
            catchment_summary_dict[catchment]["lineage"] = get_top_10_str(total,catchment_summary_dict[catchment]["lineage"])


    return catchment_summary_dict

def get_full_metadata(config):

    query_metadata = []
    with open(config[KEY_QUERY_METADATA]) as f:
        reader = csv.DictReader(f)
        for row in reader:
            query_metadata.append(row)
    
    return json.dumps(query_metadata)


def get_timeline(catchment, config):

    timeline_data = timeline_functions.make_timeline_json(catchment, config)
    
    return timeline_data

def get_query_map(config):

    qmap_data = map_functions.make_query_map_json(config)

    return qmap_data

def get_background_map(config):

    bmap_data = map_functions.make_background_map_json(config)

    return bmap_data

def get_snipit(catchments,data_for_report,config):
    for catchment in catchments:
        snipit_svg = ""
        with open(os.path.join(config["tempdir"],"snipit",f"{catchment}.snipit.svg"),"r") as f:
            for l in f:
                l = l.rstrip("\n")
                snipit_svg+=f"{l}\n"
        data_for_report[catchment]["snipit_svg"] = snipit_svg

def get_nexus(catchments,data_for_report,config):
    for catchment in catchments:
        nexus = ""
        with open(os.path.join(config["outdir"],"catchments",f"{catchment}.tree"),"r") as f:
            for l in f:
                l = l.rstrip("\n")
                nexus+=f"{l}\n"
        data_for_report[catchment]["nexus"] = nexus.rstrip("\n")

def get_background_data(metadata,config):
    background_data = {}

    with open(metadata,"r") as f:
        reader = csv.DictReader(f)
        background_columns = []
        for i in [config[KEY_INPUT_DISPLAY_COLUMN],config[KEY_SEQUENCE_ID_COLUMN],"lineage",config[KEY_BACKGROUND_LOCATION_COLUMN],config[KEY_BACKGROUND_DATE_COLUMN],config[KEY_INPUT_DATE_COLUMN]]:
            if i in reader.fieldnames:
                background_columns.append(i)
        for row in reader:
            data = {}
            for i in background_columns:
                data[i] = row[i]
            if row[KEY_QUERY_BOOLEAN] == "True":
                data["Query"] = "True"
                background_data[row[config[KEY_INPUT_DISPLAY_COLUMN]]] = data
            else:
                data["Query"] = "False"
                background_data[row[config[KEY_INPUT_DISPLAY_COLUMN]]] = data
    data = json.dumps(background_data) 
    return data

def get_global_snipit(data_for_report,config):
    global_snipit_svg = ""
    with open(os.path.join(config["tempdir"],"snipit", "global_snipit.svg"),"r") as f:
        for l in f:
            l = l.rstrip("\n")
            global_snipit_svg+=f"{l}\n"
    data_for_report["global_snipit_svg"] = global_snipit_svg


def define_report_content(metadata,catchments,figure_catchments,config):
    report_content = config[KEY_REPORT_CONTENT]
    catchment_id = 0
    data_for_report = {}
    for catchment in catchments:
        data_for_report[catchment] = {}
        catchment_id += 1
        data_for_report[catchment]["catchmentID"]=f"catchment_{catchment_id}"

    if '1' in report_content:
        data_for_report[KEY_QUERY_SUMMARY_DATA] = make_query_summary_data(metadata, config)
        data_for_report[KEY_FASTA_SUMMARY_PASS],data_for_report[KEY_FASTA_SUMMARY_FAIL] = make_fasta_summary_data(metadata, config)
    else:
        data_for_report[KEY_QUERY_SUMMARY_DATA] = ""
        data_for_report[KEY_FASTA_SUMMARY_PASS],data_for_report[KEY_FASTA_SUMMARY_FAIL] = "",""
    
    if '2' in report_content:
        catchment_summary_data = make_catchment_summary_data(metadata,catchments,config)
        # returns at least a dict with total num in per catchment
        # checks for lineage col, returns lineage counts per catchment
        # checks for location col, returns location counts per catchment
        # checks for date col, finds earliest and latest dates per catchment
        # checks for SNPs col, TO DO: finds 70% consensus of catchment
        
        for catchment in catchments:
            data_for_report[catchment]["catchment_summary_data"] = catchment_summary_data[catchment]
    else:
        for catchment in catchments:
            data_for_report[catchment]["catchment_summary_data"] = ""

    if '3' in report_content:
        get_nexus(figure_catchments,data_for_report,config)
    else:
        for catchment in catchments:
            data_for_report[catchment]["nexus"] = ""
    
    if '4' in report_content:
        get_snipit(figure_catchments,data_for_report,config)
    else:
        for catchment in catchments:
            data_for_report[catchment]["snipit_svg"] = ""

    if '5' in report_content:
        for catchment in catchments:
            data_for_report[catchment]["timeline_data"] = get_timeline(catchment, config)
    else:
        for catchment in catchments:
            data_for_report[catchment]["timeline_data"] = ""
    
    if '6' in report_content:
        data_for_report["background_map_data"], data_for_report["background_map_colour_data"], seq_counts = get_background_map(config)
        data_for_report["locations_wanted"] = config[KEY_BACKGROUND_MAP_LOCATION]
        data_for_report = map_functions.get_location_information(seq_counts, config, data_for_report)
    else:
        data_for_report["background_map_data"] = ""
        data_for_report["locations_wanted"]  = ""
    
    if '7' in report_content:
        data_for_report["query_map_data"] = get_query_map(config)
    else:
        data_for_report["query_map_data"] = ""

    if '8' in report_content:
        data_for_report["full_metadata"] = get_full_metadata(config)

    if config[KEY_GLOBAL_SNIPIT]:
        get_global_snipit(data_for_report, config)
    
    return data_for_report


def make_report(metadata,report_to_generate,config):
    #need to call this multiple times if there are multiple reports wanted

    catchments = [f"catchment_{i}" for i in range(1,config["catchment_count"]+1)]
    figure_catchments = config[KEY_FIGURE_CATCHMENTS]
    data_for_report = define_report_content(metadata,catchments,figure_catchments,config)

    background_data = get_background_data(metadata,config)
    
    template_dir = os.path.abspath(os.path.dirname(config[KEY_REPORT_TEMPLATE]))
    mylookup = TemplateLookup(directories=[template_dir]) #absolute or relative works

    mytemplate = Template(filename=config[KEY_REPORT_TEMPLATE], lookup=mylookup)
    buf = StringIO()

    ctx = Context(buf, 
                    date = config[KEY_DATE], 
                    version = __version__, 
                    catchments = catchments, 
                    query_summary_data = data_for_report[KEY_QUERY_SUMMARY_DATA],
                    fasta_summary_pass = data_for_report[KEY_FASTA_SUMMARY_PASS],
                    fasta_summary_fail = data_for_report[KEY_FASTA_SUMMARY_FAIL],
                    data_for_report = data_for_report,
                    background_data = background_data,
                    config=config)

    try:
        mytemplate.render_context(ctx)
    except:
        traceback = RichTraceback()
        for (filename, lineno, function, line) in traceback.traceback:
            print("File %s, line %s, in %s" % (filename, lineno, function))
            print(line, "\n")
        print("%s: %s" % (str(traceback.error.__class__.__name__), traceback.error))

    with open(report_to_generate, 'w') as fw:
        print(green("Generating: ") + f"{report_to_generate}")
        fw.write(buf.getvalue())

