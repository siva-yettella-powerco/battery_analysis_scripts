from src.dependencies import *
from dataclasses import dataclass

@dataclass
class SupplierMetaTemplate:
    name: str
    extensions: list
    method_name: str

def detect_supplier(filepath: Path) -> str:
    '''
    detect supplier based on certain conditions for C48T project
    '''

    if 'CNMCM' in filepath.stem:
        return 'MCM'
    elif "CNSRF" in filepath.stem:
        return 'SRF'
    elif 'CNTRURON' in filepath.stem:
        return 'TRURON'
    elif 'DEBatI' in filepath.stem:
        return 'BATI'

    if ("LFP44X" in filepath.parent.stem):
        return 'MCM'

    if ("QCA0" in filepath.stem) & ("Arbitrary file name" in filepath.stem):
        return "MCM"

    if ('096_' in filepath.parent.stem) and ('_P_' in filepath.parent.stem):
        return 'SZ'


    if 'C48' in str(filepath):
        if 'MCM' in filepath.stem:
            return 'MCM'
        elif "CNSRF" in filepath.stem:
            return 'SRF'
        elif 'CNTRURON' in filepath.stem:
            return 'TRURON'
        elif '_Channel_' in filepath.stem:
            return 'TRURON'
        elif ('Ch' in filepath.stem) and ('Wb' in filepath.stem):
            return 'TRURON'
        elif 'DQ' == filepath.stem[:2]:
            return 'GOTION'
        elif '_DQ' in filepath.stem:
            return 'GOTION'
        elif 'LAB-VW' == filepath.stem[:6]:
            return 'GOTION'
        elif 'GOT' in filepath.stem:
            return 'MCM'
        elif 'BatI' in filepath.stem:
            return 'BATI'
        else:
            if ('B1_sample' in str(filepath)) and ('FCA' in filepath.stem):
                return 'MCM'
            elif ('B1DOE' in str(filepath)):
                return 'MCM'

    if 'C25T1' in str(filepath):
        if 'CNMCM' in filepath.stem:
            return 'MCM'
        elif "CNSRF" in filepath.stem:
            return 'SRF'
        elif 'DQ' == filepath.stem[:2]:
            return 'GOTION'
        elif '_DQ' in filepath.stem:
            return 'GOTION'


    return 'UNKNOWN'

FOCUS_COLS_ETL = ['Total_time_s', 'Date_time','Unix_time', 'Step', 'Step_name', 'Cycle', 'Voltage_V',
       'Current_A', 'Power_W', 'Capacity_step_Ah', 'Energy_step_Wh',
       'T_Cell_degC', 'T_Anode_degC', 'T_Cathode_degC', 'T_Chamber_degC','T_cold_degC']

MANDATORY_COLS_ETL = ['Total_time_s','Date_time','Voltage_V', 'Current_A', 'Capacity_step_Ah']
