import os
import logging
from logging.config import dictConfig
import copy
import pandas as pd

# visualize
import matplotlib.pyplot as plt
import seaborn as sns
sns.set_style("darkgrid")
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams["figure.autolayout"] = True

# font
import matplotlib.font_manager as fm
font_list = [font.name for font in fm.fontManager.ttflist]
plt.rcParams['font.family'] = 'Malgun Gothic'

# logging
from src.utils import generate_logger, timeit, load_data
dictConfig(generate_logger(__name__))
logger = logging.getLogger(__name__)

# directory
App_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))
Data_dir = os.path.join(App_dir, 'data')
Result_dir = os.path.join(App_dir, 'result')


class EDA:
    def __init__(self,
                 codebook_name: str,
                 PV_var: int):
        assert type(codebook_name) == str
        assert type(PV_var) == int

        self.data = load_data(os.path.join(App_dir, 'data', 'cleaned.pkl'))
        self.cb = pd.read_excel(os.path.join(Data_dir, codebook_name))
        self.PV_var = PV_var

        self.nation_real_name = {'SK': '대한민국', 'US': '미국'}
        self.data_final = {'full': {'SK': pd.DataFrame(), 'US': pd.DataFrame()},
                        'sliced': {'SK': pd.DataFrame(), 'US': pd.DataFrame()}}
    
    def join_splited_data(self):
        r"""
        join student, school and teacher dataframe at once
        """
        logger.debug(f'step1. join dataframe')
        data_1_join = dict()

        for nationalName, inputNational in self.data.items():
            df_student = inputNational[0].copy()
            df_school = inputNational[1].copy()
            df_teacher = inputNational[2].copy()
            logger.debug(f'student data: {df_student.shape}')
            logger.debug(f'school data: {df_school.shape}')
            logger.debug(f'teacher data: {df_teacher.shape}')
            
            df_student.reset_index(drop=True, inplace=True)
            rs = copy.deepcopy(df_student)
            before = df_student.shape

            # if school data exists, merge it
            if df_school.shape[1] <= EDA._demographic_column_count(self):
                logger.critical('school data is empty')
            else:
                EDA._match_info(data_ref=df_student, data=df_school)
            
            # if teacher data exists, merge it
            if df_teacher.shape[1] <= EDA._demographic_column_count(self):
                logger.critical('teacher data is empty')
            else:
                EDA._match_info(data_ref=df_student, data=df_teacher)

            after = rs.shape
            logger.debug(f'Bef: {before}, Aft: {after}')
            data_1_join[nationalName] = rs
        
        self.data_1_join = data_1_join
        return data_1_join
        
    @timeit
    def drop_student(self,
                     na_threshold: int,
                     is_visualize=False):
        r"""
        drop student who have many NA

        Parameters
        ----------
        na_threshold: int
            remove rows that contain more than a threshold numbver of NA values.
        """
        logger.debug(f'step2. Verify na and Drop student')
        def column_wise_NA(inputData) -> dict:
            r"""generate column-wise NA ratio"""
            if type(inputData) == dict:
                merged = pd.concat([inputData['SK'], inputData['US']])
                assert merged.shape[0] == inputData['SK'].shape[0] + inputData['US'].shape[0]
            
            elif type(inputData) == pd.DataFrame:
                merged = copy.deepcopy(inputData)
            
            else:
                raise TypeError('dictionary or pd.DataFrame is allowed')
            
            describeDF = merged.describe().T
            describeDF['NA_ratio'] = round(100 - describeDF['count']/merged.shape[0]*100, 2)

            newColumnOrder = [describeDF.columns[0], 'NA_ratio'] + list(describeDF.columns[1:-1])
            describeDF= describeDF[newColumnOrder]
            return describeDF

        # student-wise data validation
        def row_wise_NA(inputData: dict, is_visualize: bool, na_threshold: int) -> dict:
            r"""calculate NA ratio per student"""
            merged = pd.concat([inputData['SK'], inputData['US']])
            assert merged.shape[0] == inputData['SK'].shape[0] + inputData['US'].shape[0]

            for_histogram = {}
            rs = {}
            for label, data in zip(['full', 'SK', 'US'], [merged, inputData['SK'], inputData['US']]):
                for_histogram[label] = []
                to_drop = []

                for i in range(len(data.index)) :
                    na_cnt = data.iloc[i].isnull().sum()
                    na_ratio = round((na_cnt/data.shape[1]) * 100, 0)
                    for_histogram[label].append(na_ratio)
                    if na_cnt > na_threshold:
                        to_drop.append(i)
                logger.debug(f'NA drop of {label}: {len(to_drop)}')
                rs[label] = data.drop(to_drop, axis=1)

            if is_visualize == True:
                plt.figure(figsize=(17,6))

                plt.subplot(1, 3, 1)
                plt.hist(for_histogram['full'])
                plt.title('\nFull Data\n')
                plt.xlabel('\nNA ratio(%)\n')
                plt.ylabel('frequency')
                
                plt.subplot(1, 3, 2)
                plt.hist(for_histogram['SK'])
                plt.title('\nSouth Korea\n')
                plt.xlabel('\nNA ratio(%)\n')
                plt.ylabel('frequency')
                
                plt.subplot(1, 3, 3)
                plt.hist(for_histogram['US'])
                plt.title('\nUnited States\n')
                plt.xlabel('\nNA ratio(%)\n')
                plt.ylabel('frequency')

                plt.savefig(os.path.join(Data_dir, f'NA_ratio.png'))

            return rs
        
        self.rs_deescriptive_Full = column_wise_NA(self.data_1_join)
        self.rs_deescriptive_SK = column_wise_NA(self.data_1_join['SK'])
        self.rs_deescriptive_US = column_wise_NA(self.data_1_join['US'])

        clean_data_using_rowwise_NA = row_wise_NA(self.data_1_join, na_threshold=na_threshold, is_visualize=is_visualize)
        self.data_2_dropNA = {
            "SK": clean_data_using_rowwise_NA['SK'],
            "US": clean_data_using_rowwise_NA['US']
        }
        return self.data_2_dropNA
    

    def slice_by_ESCS(self,
                      acad_threshold: int,
                      is_visualize=False) -> dict:
        r"""
        calculate ESCS variable and devide dataset by full and sliced
        
        Parameters
        ----------
        acad_threshold: int
            academic score thrshold
        """
        logger.debug('step3. slice data by ESCS')

        def visualize(data: dict, option: str, threshold_info: dict,
                    figName: str):
            r"""visualize threshold and ratio of sample distribution

            Parameters
            ----------
            option: str
                full or sliced
            figName: str
                title of figure
            """
            plt.figure(figsize=(17,9))
            for IDX, (nationalName, inputNational) in enumerate(data.items()):

                plt.subplot(2, 2, 2*IDX+1)
                plt.hist(inputNational['AcademicScore'])
                plt.title(f'\nAcademic Achievement{self.nation_real_name[nationalName]}\n')
                plt.xlabel('\nScore\n')
                plt.axvline(threshold_info[nationalName]['academic_score'], color='r', linewidth=1, linestyle='--')
                
                plt.subplot(2, 2, 2*IDX+2)
                plt.hist(inputNational['ESCS'])
                plt.title(f'\nESCS{self.nation_real_name[nationalName]}\n')
                plt.xlabel('\nScore\n')
                if option=='full':
                    plt.axvline(threshold_info[nationalName]['escs_score'], color='r', linewidth=1, linestyle='--')
                
            plt.savefig(os.path.join(Result_dir, f'{figName}_{option}.png'))
        
        ## 1. calculate threshold value
        threshold_info, data_appended = EDA.thresholdCalculator(self.data_2_dropNA,
                                                            PV_var = self.PV_var,
                                                            acad_threshold = acad_threshold) ##!#!## 학업성취 코딩 방법을 바꿀 때 여기 arg를 조정
        
        
        ## 2. slice
        data_3_ESCS = {
            "full": copy.copy(data_appended), # no drop case, so just copied
            "sliced": EDA.slice_data_by_escs(data_appended, escsThreshold = threshold_info)
        }
        assert type(data_3_ESCS['full']) == dict


        ## 3. labeling resilient student
        data_3_ESCS['full'] = EDA.labeling_resilient(data = data_3_ESCS['full'], 
                                                option = 'full',
                                                threshold_info = threshold_info)
        data_3_ESCS['sliced'] = EDA.labeling_resilient(data = data_3_ESCS['sliced'], 
                                                option = 'sliced',
                                                threshold_info = threshold_info)
        self.data_3_ESCS = data_3_ESCS
        
        ## 4. visualize resilient student
        if is_visualize == True:
            resilientCount_Ratio_full = EDA.table_resilient_ratio(data=self.data_3_ESCS['full'])
            resilientCount_Ratio = EDA.table_resilient_ratio(data=self.data_3_ESCS['sliced'])
        
            visualize(self.data_3_ESCS['full'], option='full', figName=f'Read{self.PV_var}', threshold_info= threshold_info)
            visualize(self.data_3_ESCS['sliced'], option = 'sliced', figName =f'Read{self.PV_var}(target paper)', threshold_info= threshold_info)
        
            logger.debug(f"# of academic resilient student(full): {resilientCount_Ratio_full}")
            logger.debug(f'# of academic resilient student(sliced): {resilientCount_Ratio}')
            return resilientCount_Ratio
        return data_3_ESCS
    
    def minor_adjustment(self):
        r"""adjust minor things
        - merge two country dataframe
        - drop PV value (not predictor)
        - reorder column
        """
        logger.debug('step4. adjust miscellanous thing, like column order, drop unnecessary column')
        def merge_country(inputData: dict) -> pd.DataFrame:
            output = pd.concat([inputData['SK'], inputData['US']], axis=0)
            assert inputData['SK'].shape[0] + inputData['US'].shape[0] == output.shape[0]
            return output
        
        def drop_useless_column(inputData: pd.DataFrame) -> pd.DataFrame:
            dropAcademic = ['CNTRYID', 'AcademicScore']
            for column in inputData.columns:
                if 'PV' in column:
                    dropAcademic.append(column)
            return inputData.drop(dropAcademic, axis=1)

        def columnOrder(inputData: pd.DataFrame,
                        important_columns=['resilient']) -> pd.DataFrame:
            r"""for convinient in further analysis, columns are reordered"""
            column_ID = ['CNT', 'CNTSCHID', 'CNTSTUID']
            inputData.set_index(column_ID+important_columns, inplace=True)
            inputData.reset_index(inplace=True)
            return inputData

        tmp_full = merge_country(self.data_3_ESCS['full'])
        tmp_sliced = merge_country(self.data_3_ESCS['sliced'])
        
        tmp2_full = drop_useless_column(tmp_full)
        tmp2_sliced = drop_useless_column(tmp_sliced)

        self.data_final['full'] = columnOrder(tmp2_full)
        self.data_final['sliced'] = columnOrder(tmp2_sliced)
        return self.data_final

    @staticmethod
    def thresholdCalculator(data: dict,
                            PV_var: int,
                            acad_threshold: int):
        r"""calculate 2 kinds of threshold, and append mean column in data"""
        assert type(PV_var) == int, 'insert valid PV_var type'
        assert type(acad_threshold) == int, 'insert valid threshold type'
        assert (PV_var > 0) and (PV_var < 11), print('>> Error__PV_var: ', PV_var)

        threshold_dict = {'SK': {'academic_score': acad_threshold}, 'US': {'academic_score': acad_threshold}}
        targetColumn = ['PV'+ str(PV_var) + 'READ']
        rs = data.copy()

        for nationalName, inputNational in data.items():
            rs[nationalName]['AcademicScore'] = inputNational.loc[:, targetColumn].mean(axis=1)
            inputNational = inputNational.astype({'ESCS': "float64"})
            threshold_dict[nationalName]['escs_score'] = inputNational['ESCS'].quantile(0.25)

        return threshold_dict, rs
    
    @staticmethod
    def slice_data_by_escs(data: dict,
                           escsThreshold: dict) -> dict:
        r"""slice data by escs score"""
        assert type(data) == dict, 'insert valid data'
        assert type(escsThreshold) == dict, 'insert valid threshold'

        rs = {'SK': pd.DataFrame(), 'US': pd.DataFrame()}
        for nationalName, inputNational in data.items():
            before = inputNational.shape[0]
            toDrop = []
            for idx, val in zip(inputNational['ESCS'].index, inputNational['ESCS'].values):
                if val < escsThreshold[nationalName]['escs_score']:
                    continue
                else:
                    toDrop.append(idx)
            
            rs[nationalName] = inputNational.drop(toDrop, axis=0)
            after = rs[nationalName].shape[0]
            logger.debug(f'>> before: {before} >> after: {after}' )
        
        return rs
    
    @staticmethod
    def labeling_resilient(data: dict,
                           option: str,
                           threshold_info: dict):
        r"""
        decide whether student have resilience or not

        Parameters
        ----------
        option: str
            full or sliced

        if condition1: using academic score
            & condition2: using escs score
            full: condition1 & condition2
            sliced: condition1
            - since sliced data already sliced by escs score
        """
        if (option == 'full') or (option == 'sliced'): pass
        else: raise ValueError('input valid option args')
            
        assert type(threshold_info) == dict
        rs = {'SK': pd.DataFrame(), 'US': pd.DataFrame()}
        
        for nationalName, inputNational in data.items():
            threshold_acad = threshold_info[nationalName]['academic_score']
            threshold_escs = threshold_info[nationalName]['escs_score']
            
            iamResilient = []
            for idx in inputNational.index:
                val_acad = inputNational.loc[idx, 'AcademicScore']
                val_escs = inputNational.loc[idx, 'ESCS']
                if option == 'full':
                    if (val_acad > threshold_acad) and (val_escs < threshold_escs):
                        iamResilient.append(1)
                    else: iamResilient.append(0)
                elif option == 'sliced':
                    if val_acad > threshold_acad:
                        iamResilient.append(1)
                    else: iamResilient.append(0)

            inputNational['resilient'] = iamResilient
            rs[nationalName] = inputNational.copy()

        return rs
    
    @staticmethod
    def table_resilient_ratio(data: dict) -> dict:
        r"""calculate ratio of resilient student compared with full
        """
        count_ratio = {'SK': [], 'US': []}
        for nationalName in count_ratio.keys():
            total = data[nationalName].shape[0]
            is_resilient = data[nationalName]['resilient'].values

            resilientCount = [x for x in is_resilient if x == 1]
            resilientRatio = round(len(resilientCount)/total * 100, 2)
            count_ratio[nationalName].append(len(resilientCount))
            count_ratio[nationalName].append(resilientRatio)
            logger.debug(f'회복탄력성 보유 학생수({nationalName}): , {len(resilientCount)}, ({resilientRatio})%')
        return count_ratio
 
    def save_result(self):
        r"""save attributes"""
        save_dir = os.path.join(App_dir, 'result')
        if not os.path.isdir(save_dir): os.mkdir(save_dir)
            
        with pd.ExcelWriter(os.path.join(save_dir, f"preprocessing{self.PV_var}.xlsx")) as writer:
            self.data_final['full'].to_excel(writer, sheet_name = "full", index=False)
            self.data_final['sliced'].to_excel(writer, sheet_name = "sliced", index=False)
    
    def _demographic_column_count(self) -> int:
        r"""count demographic columns
        
        Note
        -----
        in codebook, demographic variable should labeled as 'identifier'
        """
        identifier_cb = self.cb[self.cb['category']=='identifier']
        return identifier_cb.shape[0]
        

def main(PV: int,
         is_visualize: bool):
    assert (PV < 11) and (PV > 0), f"invalid argument PV, only int from 1 to 10 is allowed"

    eda = EDA(codebook_name='codebook.xlsx', PV_var=PV)
    eda.join_splited_data()
    eda.drop_student(na_threshold=30, is_visualize = is_visualize)
    eda.slice_by_ESCS(acad_threshold=480, is_visualize = is_visualize)
    eda.minor_adjustment()
    eda.save_result()