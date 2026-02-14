import pandas as pd

from TB_CPA_TestDataAutomation.src.dependencies import *
from .supplier_support_func.hm_general_support import gen_clean_datasheet
from .supplier_support_func.hm_gen_trans_func import gen_apply_transform_raw_data
from .hm_supplier_config import detect_supplier, FOCUS_COLS_ETL, MANDATORY_COLS_ETL
from .supplier_support_func.hm_mcm_trans_func import *

class cfg_mcm_std_01:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)

    def get_sheet_names(self):
        raw_xl = pd.ExcelFile(self.filepath)
        return raw_xl.sheet_names

    def get_raw_data(self,config_selected)->pd.DataFrame:
        raw_data = pd.read_excel(self.filepath, sheet_name=None)
        sheet_names_matching = [sheet for sheet in raw_data.keys() if
                                fnmatch.fnmatch(sheet, config_selected['Datasheet'])]
        out_df = pd.DataFrame([])
        # loop over matching datasheets
        for i in sheet_names_matching:
            if raw_data[i].shape[0]>1:
                # clean the sheet data for headers & get config_to_file_column mapping
                # TODO Values are still not converted from str to numeric in gen_clean_datasheet
                sheet_check_flg, cleaned_sheet, header_map = gen_clean_datasheet(sheet_df=raw_data[i],
                                                config_selected=config_selected, focus_cols=FOCUS_COLS_ETL,
                                                                            mandatory_cols=MANDATORY_COLS_ETL)
                # concat sheets which are okay after cleaned
                if sheet_check_flg:
                    out_df = pd.concat([out_df, cleaned_sheet], axis=0)
                else:
                    logging.warning(f"Sheet check failed in gen_clean_datasheet(): {i} in file {self.filepath.name}")

            else:
                sheet_check_flg = False
                logging.warning(f"Sheet empty: {i} in file {self.filepath.name}")

        return out_df

class cfg_mcm_std_02:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)

    def get_sheet_names(self):
        raw_xl = pd.ExcelFile(self.filepath)
        return raw_xl.sheet_names

    def get_raw_data(self,config_selected)->pd.DataFrame:
        raw_data = pd.read_excel(self.filepath, sheet_name=None)
        sheet_names_matching = [sheet for sheet in raw_data.keys() if
                                fnmatch.fnmatch(sheet, config_selected['Datasheet'])]
        out_df = pd.DataFrame([])
        # loop over matching datasheets
        for i in sheet_names_matching:
            if raw_data[i].shape[0]>1:
                # clean the sheet data for headers & get config_to_file_column mapping
                # TODO Values are still not converted from str to numeric in gen_clean_datasheet
                sheet_check_flg, cleaned_sheet, header_map = gen_clean_datasheet(sheet_df=raw_data[i],
                                                config_selected=config_selected, focus_cols=FOCUS_COLS_ETL,
                                                                            mandatory_cols=MANDATORY_COLS_ETL)
                # concat sheets which are okay after cleaned
                if sheet_check_flg:
                    out_df = pd.concat([out_df, cleaned_sheet], axis=0)
                else:
                    logging.warning(f"Sheet check failed in gen_clean_datasheet(): {i} in file {self.filepath.name}")

            else:
                sheet_check_flg = False
                logging.warning(f"Sheet empty: {i} in file {self.filepath.name}")

        return out_df

class cfg_mcm_exp_02:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)

    def get_sheet_names(self):
        raw_xl = pd.ExcelFile(self.filepath)
        return raw_xl.sheet_names

    def get_raw_data(self,config_selected)->pd.DataFrame:
        raw_data = pd.read_excel(self.filepath, sheet_name=None)

        sheet_names_matching = [sheet for sheet in raw_data.keys() if
                                fnmatch.fnmatch(sheet, config_selected['Datasheet'])]
        out_df = pd.DataFrame([])
        # loop over matching datasheets
        for i in sheet_names_matching:
            if raw_data[i].shape[0]>1:
                # clean the sheet data for headers & get config_to_file_column mapping
                # TODO Values are still not converted from str to numeric in gen_clean_datasheet
                sheet_check_flg, cleaned_sheet, header_map = gen_clean_datasheet(sheet_df=raw_data[i],
                                                config_selected=config_selected, focus_cols=FOCUS_COLS_ETL,
                                                                            mandatory_cols=MANDATORY_COLS_ETL)
                # concat sheets which are okay after cleaned
                if sheet_check_flg:
                    out_df = pd.concat([out_df, cleaned_sheet], axis=0)
                else:
                    logging.warning(f"Sheet check failed in gen_clean_datasheet(): {i} in file {self.filepath.name}")

            else:
                sheet_check_flg = False
                logging.warning(f"Sheet empty: {i} in file {self.filepath.name}")

        return out_df

class cfg_mcm_xls_01:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)

    def get_sheet_names(self):
        # no sheet name for .xls files
        return ['Data']

    def get_raw_data(self,config_selected)->pd.DataFrame:
        raw_data, import_check = convert_mcm_xls_to_df(input_path=self.filepath)

        if not import_check:
            logging.warning(f'Error while converting .XLS file to dataframe {self.filepath.name}')

        sheet_names_matching = [sheet for sheet in raw_data.keys() if
                                fnmatch.fnmatch(sheet, config_selected['Datasheet'])]
        out_df = pd.DataFrame([])
        # loop over matching datasheets
        for i in sheet_names_matching:
            if raw_data[i].shape[0]>1:
                # clean the sheet data for headers & get config_to_file_column mapping
                # TODO Values are still not converted from str to numeric in gen_clean_datasheet
                sheet_check_flg, cleaned_sheet, header_map = gen_clean_datasheet(sheet_df=raw_data[i],
                                                config_selected=config_selected, focus_cols=FOCUS_COLS_ETL,
                                                                            mandatory_cols=MANDATORY_COLS_ETL)
                # concat sheets which are okay after cleaned
                if sheet_check_flg:
                    out_df = pd.concat([out_df, cleaned_sheet], axis=0)
                else:
                    logging.warning(f"Sheet check failed in gen_clean_datasheet(): {i} in file {self.filepath.name}")
            else:
                sheet_check_flg = False
                logging.warning(f"Sheet empty: {i} in file {self.filepath.name}")

        return out_df

class cfg_srf_std_01:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)

    def get_sheet_names(self):
        raw_xl = pd.ExcelFile(self.filepath)
        return raw_xl.sheet_names

    def get_raw_data(self,config_selected)->pd.DataFrame:
        raw_data = pd.read_excel(self.filepath, sheet_name=None)
        sheet_names_matching = [sheet for sheet in raw_data.keys() if
                                fnmatch.fnmatch(sheet, config_selected['Datasheet'])]
        out_df = pd.DataFrame([])
        # loop over matching datasheets
        for i in sheet_names_matching:
            if raw_data[i].shape[0]>1:
                # clean the sheet data for headers & get config_to_file_column mapping
                # TODO Values are still not converted from str to numeric in gen_clean_datasheet
                sheet_check_flg, cleaned_sheet, header_map = gen_clean_datasheet(sheet_df=raw_data[i],
                                                config_selected=config_selected, focus_cols=FOCUS_COLS_ETL,
                                                                            mandatory_cols=MANDATORY_COLS_ETL)
                # concat sheets which are okay after cleaned
                if sheet_check_flg:
                    out_df = pd.concat([out_df, cleaned_sheet], axis=0)
                else:
                    logging.warning(f"Sheet check failed in gen_clean_datasheet(): {i} in file {self.filepath.name}")

            else:
                sheet_check_flg = False
                logging.warning(f"Sheet empty: {i} in file {self.filepath.name}")

        return out_df

class cfg_srf_std_01:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)

    def get_sheet_names(self):
        try:
            raw_xl = pd.ExcelFile(self.filepath)
            return raw_xl.sheet_names
        except Exception as e:
            logging.critical(f"couldn't get sheet names for {self.filepath.stem}")
            logging.debug(f"Debug message: {e}")
            return [">>nonefound<<"]


    def get_raw_data(self,config_selected)->pd.DataFrame:
        raw_data = pd.read_excel(self.filepath, sheet_name=None)
        sheet_names_matching = [sheet for sheet in raw_data.keys() if
                                fnmatch.fnmatch(sheet, config_selected['Datasheet'])]
        out_df = pd.DataFrame([])
        # loop over matching datasheets
        for i in sheet_names_matching:
            if raw_data[i].shape[0]>1:
                # clean the sheet data for headers & get config_to_file_column mapping
                # TODO Values are still not converted from str to numeric in gen_clean_datasheet
                sheet_check_flg, cleaned_sheet, header_map = gen_clean_datasheet(sheet_df=raw_data[i],
                                                config_selected=config_selected, focus_cols=FOCUS_COLS_ETL,
                                                                            mandatory_cols=MANDATORY_COLS_ETL)
                # concat sheets which are okay after cleaned
                if sheet_check_flg:
                    out_df = pd.concat([out_df, cleaned_sheet], axis=0)
                else:
                    logging.warning(f"Sheet check failed in gen_clean_datasheet(): {i} in file {self.filepath.name}")
            else:
                sheet_check_flg = False
                logging.warning(f"Sheet empty: {i} in file {self.filepath.name}")

        return out_df

class cfg_got_std_01:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)

    def get_sheet_names(self):
        try:
            raw_xl = pd.ExcelFile(self.filepath)
            return raw_xl.sheet_names
        except Exception as e:
            logging.critical(f"couldn't get sheet names for {self.filepath.stem}")
            logging.debug(f"Debug message: {e}")
            return [">>nonefound<<"]


    def get_raw_data(self,config_selected)->pd.DataFrame:
        raw_data = pd.read_excel(self.filepath, sheet_name=None)
        sheet_names_matching = [sheet for sheet in raw_data.keys() if
                                fnmatch.fnmatch(sheet, config_selected['Datasheet'])]
        out_df = pd.DataFrame([])
        # loop over matching datasheets
        for i in sheet_names_matching:
            if raw_data[i].shape[0]>1:
                # clean the sheet data for headers & get config_to_file_column mapping
                # TODO Values are still not converted from str to numeric in gen_clean_datasheet
                sheet_check_flg, cleaned_sheet, header_map = gen_clean_datasheet(sheet_df=raw_data[i],
                                                config_selected=config_selected, focus_cols=FOCUS_COLS_ETL,
                                                                            mandatory_cols=MANDATORY_COLS_ETL)
                # concat sheets which are okay after cleaned
                if sheet_check_flg:
                    out_df = pd.concat([out_df, cleaned_sheet], axis=0)
                else:
                    logging.warning(f"Sheet check failed in gen_clean_datasheet(): {i} in file {self.filepath.name}")
            else:
                sheet_check_flg = False
                logging.warning(f"Sheet empty: {i} in file {self.filepath.name}")

        return out_df

class cfg_tru_std_01:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)

    def get_sheet_names(self):
        try:
            raw_xl = pd.ExcelFile(self.filepath)
            return raw_xl.sheet_names
        except Exception as e:
            logging.critical(f"couldn't get sheet names for {self.filepath.stem}")
            logging.debug(f"Debug message: {e}")
            return [">>nonefound<<"]


    def get_raw_data(self,config_selected)->pd.DataFrame:
        raw_data = pd.read_excel(self.filepath, sheet_name=None)
        sheet_names_matching = [sheet for sheet in raw_data.keys() if
                                fnmatch.fnmatch(sheet, config_selected['Datasheet'])]
        out_df = pd.DataFrame([])
        # loop over matching datasheets
        for i in sheet_names_matching:
            if raw_data[i].shape[0]>1:
                # clean the sheet data for headers & get config_to_file_column mapping
                # TODO Values are still not converted from str to numeric in gen_clean_datasheet
                sheet_check_flg, cleaned_sheet, header_map = gen_clean_datasheet(sheet_df=raw_data[i],
                                                config_selected=config_selected, focus_cols=FOCUS_COLS_ETL,
                                                                            mandatory_cols=MANDATORY_COLS_ETL)
                # concat sheets which are okay after cleaned
                if sheet_check_flg:
                    out_df = pd.concat([out_df, cleaned_sheet], axis=0)
                else:
                    logging.warning(f"Sheet check failed in gen_clean_datasheet(): {i} in file {self.filepath.name}")
            else:
                sheet_check_flg = False
                logging.warning(f"Sheet empty: {i} in file {self.filepath.name}")

        return out_df

class cfg_got_c32_01:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)

    def get_sheet_names(self):
        raw_xl = pd.ExcelFile(self.filepath)
        return raw_xl.sheet_names

    def get_raw_data(self,config_selected)->pd.DataFrame:
        raw_data = pd.read_excel(self.filepath, sheet_name=None)
        sheet_names_matching = [sheet for sheet in raw_data.keys() if
                                fnmatch.fnmatch(sheet, config_selected['Datasheet'])]
        out_df = pd.DataFrame([])
        # loop over matching datasheets
        for i in sheet_names_matching:
            if raw_data[i].shape[0]>1:
                # clean the sheet data for headers & get config_to_file_column mapping
                # TODO Values are still not converted from str to numeric in gen_clean_datasheet
                sheet_check_flg, cleaned_sheet, header_map = gen_clean_datasheet(sheet_df=raw_data[i],
                                                config_selected=config_selected, focus_cols=FOCUS_COLS_ETL,
                                                                            mandatory_cols=MANDATORY_COLS_ETL)
                # concat sheets which are okay after cleaned
                if sheet_check_flg:
                    out_df = pd.concat([out_df, cleaned_sheet], axis=0)
                else:
                    logging.warning(f"Sheet check failed in gen_clean_datasheet(): {i} in file {self.filepath.name}")
            else:
                sheet_check_flg = False
                logging.warning(f"Sheet empty: {i} in file {self.filepath.name}")

        return out_df

class cfg_sz_std_01:
    def __init__(self, filepath: Path):
        self.filepath = Path(filepath)

    def get_sheet_names(self):
        return ["unknown_sheet_csv"]

    def get_raw_data(self, config_selected) -> pd.DataFrame:
        raw_data = pd.read_csv(self.filepath,encoding="ISO-8859-1", sep=';', skiprows=[1])

        out_df = pd.DataFrame([])
        # loop over matching datasheets

        if raw_data.shape[0] > 1:
            # clean the sheet data for headers & get config_to_file_column mapping
            # TODO Values are still not converted from str to numeric in gen_clean_datasheet
            sheet_check_flg, cleaned_sheet, header_map = gen_clean_datasheet(sheet_df=raw_data,
                                                                             config_selected=config_selected,
                                                                             focus_cols=FOCUS_COLS_ETL,
                                                                             mandatory_cols=MANDATORY_COLS_ETL)
            # concat sheets which are okay after cleaned
            if sheet_check_flg:
                out_df = pd.concat([out_df, cleaned_sheet], axis=0)
            else:
                logging.warning(
                    f"Sheet check failed in gen_clean_datasheet(): {i} in file {self.filepath.name}")

        else:
            sheet_check_flg = False
            logging.warning(f"Sheet empty: {i} in file {self.filepath.name}")

        return out_df

def find_matching_config(file_path:Path, etl_df:pd.DataFrame, hm_status_dict:defaultdict) -> tuple[str|None,defaultdict]:
    file_id = str(file_path)
    hm_status_dict[file_id]['file_name'] = file_path.name
    hm_status_dict[file_id]['file_type'] = file_path.suffix
    try:
        hm_status_dict[file_id]['file_format_act'] = magic.from_file(file_id)
    except Exception as e:
        logging.warning(f'Failed to use python-magic for file format detection {file_path.name}')
        logging.debug(f'Debug Message: {e}')
    hm_status_dict[file_id]['supplier_name'] = detect_supplier(file_path)

    # --------------------------------------------------------
    # --------------- Find matching configuration -----------
    # --------------------------------------------------------
    # filter configs with Supplier_id and file format
    match_configs_df = etl_df[(etl_df['Supplier_id'] == detect_supplier(file_path)) &
                              (etl_df['Pattern'].apply(lambda p: fnmatch.fnmatch(file_path.name.lower(), p)))]
    match_configs_df['sheet_match_flg'] = False
    # loop over the matching configs and check for right config based on DataSheets
    if match_configs_df.shape[0] > 0:
        for indx in match_configs_df.index:
            #print('Running config row:', match_configs_df.loc[indx, 'Config_id'])
            # calls the relevant config class in hm_import_data.py
            if match_configs_df.loc[indx, 'Config_id'] in globals().keys():
                cfg_cls = globals()[match_configs_df.loc[indx, 'Config_id']](file_path)
                # find all data sheets available using the method get_sheet_names() for cfg class and
                # find matching ones as per "Datasheet" pattern given in config file
                all_sheet_names = cfg_cls.get_sheet_names()
                sheet_names_matching = [sheet for sheet in all_sheet_names if
                                        fnmatch.fnmatch(sheet, match_configs_df.loc[indx, 'Datasheet'])]
                #print(match_configs_df.loc[indx, 'Datasheet'])
                match_configs_df.loc[indx, 'sheet_match_flg'] = any(sheet_names_matching)
            else:
                match_configs_df.loc[indx, 'sheet_match_flg'] = False
        # filter configs after Datasheet name checks
        match_configs_df = match_configs_df[match_configs_df['sheet_match_flg']]

        if match_configs_df.shape[0] > 0:
            if match_configs_df.shape[0] > 1:
                logging.warning(f'Found mutiple config matches <{match_configs_df["Config_id"].to_list()}> for file: '
                                f'<{file_path.name}>')
            # -------- TODO: simplified assuming by datasheet check only one config would be valid --------
            # -------- but in future, check for available column names to match the config ----------
            config_selected = match_configs_df.iloc[0]
            hm_status_dict[file_id]['matching_config'] = config_selected['Config_id']

        else:
            hm_status_dict[file_id]['matching_config'] = None
            logging.warning(
                f'No match with {match_configs_df["Datasheet"].values} Data_sheet config: found <{all_sheet_names}> sheets in <{file_path.name}>, '
                f'supplier detected: <{detect_supplier(file_path)}>')
    else:
        hm_status_dict[file_id]['matching_config'] = None
        logging.warning(
            f'No match with any Supplier_id & Pattern: <{file_path.name}>, '
            f'supplier detected: <{detect_supplier(file_path)}>')

    return hm_status_dict[file_id]['matching_config'], hm_status_dict

def run_harmonize_with_config(file_path:Path, etl_df:pd.DataFrame, hm_status_dict:defaultdict,
                              config_name:str) -> tuple[str|None,defaultdict]:
    cfg_cls = globals()[config_name](file_path)
    config_selected = etl_df[etl_df['Config_id']==config_name].iloc[0]
    raw_clean_data = cfg_cls.get_raw_data(config_selected=config_selected)
    # TODO hm_status_dict to be updated based on the status of harmonize
    harmonized_data = gen_apply_transform_raw_data(file_data=raw_clean_data,
                                                     cfg_mapping=config_selected,
                                                     focus_columns=FOCUS_COLS_ETL)

    return harmonized_data, hm_status_dict
