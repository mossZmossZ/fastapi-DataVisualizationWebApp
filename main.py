import sqlite3
from fastapi import FastAPI, HTTPException
import json
from pydantic import BaseModel
import pandas as pd
import altair as alt
#import altair_viewer
from fastapi.middleware.cors import CORSMiddleware



app = FastAPI()

#import altair_viewer

###วิธีการใช้งาน
###pip install uvicorn
###pip install fastapi
###ตอนรัน server ให้ cd มายัง Server แล้วใช้คำสั่ง 
# uvicorn main:app --reload (macOS)
# python -m uvicorn main:app --reload (windows)
#http://127.0.0.1:8000/docs สามารถดู API ทั้งหมดได้






origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

alt.data_transformers.disable_max_rows()
# altair_viewer._global_viewer._use_bundled_js = False
# alt.data_transformers.enable('data_server')

class ChartManager():

    def __init__(self):
        self.df = None
        self.Chart = None
        #Thailand Map Chart
        self.ThailandProvincesTopo = alt.topo_feature('https://raw.githubusercontent.com/cvibhagool/thailand-map/master/thailand-provinces.topojson', 'province')
        self.obj_columns = []   #columns of object value for nomial type
        self.int_columns = []   #columns of integer value for quantitative type
    
    def setDataframe(self,dataframe):
        self.df = dataframe
        #select columns name each type
        self.obj_columns = self.df.select_dtypes(include=['object']).columns.to_list()
        self.int_columns = self.df.select_dtypes(include=['int']).columns.to_list()
    
    def ColorSchema(self,dataframe,Measurement,Color:list):
        #set color shades from max value
        color = alt.Color(Measurement,
                          type= "quantitative",
                          scale = alt.Scale(
                            domain = [0,dataframe[Measurement].mean(),dataframe[Measurement].max()],
                            range = Color,
                            type = "linear")
                        )
        return color
    
    def Tooltip(self,ColumnNames:list):
        #select tooltip type each column names
        l = []
        for col in ColumnNames:
            t = "quantitative" if col in self.int_columns else "nominal"
            l.append(alt.Tooltip(col, type= t))
        return l

    def SumDuplicateValue(self,df):
        l = []
        for y in list(set(df['year'])):
            maxweeknum = df.loc[df['year'] == y]['weeknum'].max()                       #find last week in this year
            #get dataframe with rows at last week using total_case each year
            l.append(df.loc[(df['weeknum'] == maxweeknum) & (df['year'] == y)])
        df = pd.concat(l, ignore_index=True)
        #sum total_case and deatch each province
        group = df.groupby('province').transform('sum')
        #move to dataframe
        df['total_case'] = group['total_case']
        df['total_death'] = group['total_death']
        df = df.drop_duplicates(subset=['province'])
        return df
    
    def dropAllandNone(self,df):
        #drop All and None rows
        df = df.drop(index=df[df["province"].isin(["All","None"])].index)
        return df

    def SetDatetime(self,df):
        #Change value in date column to datetime type 
        df['date'] = pd.to_datetime(
                            df['year'].astype(str) + '-W' + df['weeknum'].astype(str) + '-0',
                            format='%G-W%V-%w')
        df = df.sort_values(by=['date']).loc[df["province"]=="All"].reset_index(drop=True)
        return df
        
    def SumTotalCD(self,df):
        #sum total_case and total_case of each year for all year to allcase and alldeath
        df['allcase'] = 0
        df['alldeath'] = 0
        for index, row in df.iterrows():
            if index == 0:
                df.loc[index,'allcase'] = row['total_case']
                casenextvalue = df.loc[index,'allcase']
                df.loc[index,'alldeath'] = row['total_death']
                deathnextvalue = df.loc[index,'alldeath']
            elif index == df.shape[0] -1:
                df.loc[index,'allcase'] = casenextvalue + row['new_case']
                df.loc[index,'alldeath'] = deathnextvalue + row['new_death']
            else:
                df.loc[index,'allcase'] = casenextvalue + row['new_case']
                casenextvalue = df.loc[index,'allcase']
                df.loc[index,'alldeath'] = deathnextvalue + row['new_death']
                deathnextvalue = df.loc[index,'alldeath']
        return df

    
    def ThailandTopoChart(self,Width,Height):
        df = self.SumDuplicateValue(self.df)
        df = self.dropAllandNone(df)

        self.Chart = alt.Chart(self.ThailandProvincesTopo).mark_geoshape().encode(
            color = self.ColorSchema(df,'total_case',['white','#E34234','#640000']),
            tooltip = self.Tooltip(['properties.NAME_1','total_case','total_death'])
        ).transform_lookup(
            lookup='properties.NAME_1',
            from_ = alt.LookupData(df,'province',['total_case','total_death'])
        ).properties(
            width=Width,
            height=Height
        )

        #self.Chart.save('ChartJSON/ThailandTopoChart.json')
        return self.Chart.to_json()
    
    def BarChart(self):
        df = self.df
        df = self.dropAllandNone(df)

        self.Chart = alt.Chart(df).mark_bar(clip=True).encode(
            x = alt.X("province",type = "nominal", title= "จังหวัด"),
            y = alt.Y("total_case", 
                    type= "quantitative",
                    scale= alt.Scale(domain=[0,df["total_case"].max()]),
                    title= "ผู้ป่วยสะสม"),
            tooltip = ["province","total_case","total_death"]
        ).facet( column = "region"
        ).resolve_scale(x = 'independent',y = 'independent')

        #self.Chart.save('ChartJSON/BarChart.json')
        return self.Chart.to_json()

    def LineChart(self):
        df = self.SetDatetime(self.df)
        df = self.SumTotalCD(df)
        
        self.Chart = alt.Chart(df).mark_line(
            point=alt.OverlayMarkDef(
                filled=False, fill="white")
            ).encode(
                x=alt.X("date",type="temporal", title= "วัน"),
                y=alt.Y(
                    alt.repeat("layer"), aggregate="mean",title="ผู้ติดเชื้อสะสมทั้งประเทศ"),
                tooltip = ['date:T','allcase:Q','alldeath:Q'],
                color=alt.datum(alt.repeat("layer")),
        ).repeat(layer=["allcase", "alldeath"])

        #self.Chart.save('ChartJSON/LineChart.json')
        return self.Chart.to_json()



def plot_bar(year,country):
    conn = sqlite3.connect('./Covid.db')
    if year == 'all':
        query = "SELECT *,SUM([total_case]) AS [total_cases] FROM alldata_province_eng WHERE ([year] = 2021 OR [year] = 2023) OR ([year] = 2022 AND [weeknum] = 52) GROUP BY [province]"
        df = pd.read_sql(query , conn)
        df = df.drop('total_case', axis=1)
        df.rename(columns={"total_cases": "total_case"},inplace = True)
    else:
        if year == 2022:
            query = "SELECT * FROM alldata_province_eng WHERE [year] == %s  AND [weeknum] = 52" % year
            df = pd.read_sql(query , conn)
            
        else:
            query = "SELECT * FROM alldata_province_eng WHERE [year] == %s " % year
            df = pd.read_sql(query , conn)
    
    alt.data_transformers.disable_max_rows()
    D_country = {1:'ภาคเหนือ',2:'ภาคกลาง',3:'ภาคใต้',4:'ภาคตะวันออก',5:'ภาคตะวันตก',6:'ภาคตะวันออกเฉียงเหนือ'}
    a = len(country)

    obj = ChartManager()
    if a == 6:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])|(df['region'] == D_country[(country[4])])|(df['region'] == D_country[(country[5])])])
    elif a == 5:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])|(df['region'] == D_country[(country[4])])])
    elif a == 4:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])])
    elif a == 3:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])])
    elif a == 2:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])])
    elif a == 1:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])])
    return obj.BarChart()

def plot_line(year,country):
    conn = sqlite3.connect('./Covid.db')
    if year == 'all':
        query = "SELECT * FROM alldata_province_eng"
        df = pd.read_sql(query , conn)
        # df = df.drop('total_case', axis=1)
        # df.rename(columns={"total_cases": "total_case"},inplace = True)
    else:
        query = "SELECT * FROM alldata_province_eng WHERE [year] == %s " % year
        df = pd.read_sql(query , conn)

    
    alt.data_transformers.disable_max_rows()
    D_country = {1:'ภาคเหนือ',2:'ภาคกลาง',3:'ภาคใต้',4:'ภาคตะวันออก',5:'ภาคตะวันตก',6:'ภาคตะวันออกเฉียงเหนือ'}
    a = len(country)

    obj = ChartManager()
    if a == 6:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])|(df['region'] == D_country[(country[4])])|(df['region'] == D_country[(country[5])])])
    elif a == 5:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])|(df['region'] == D_country[(country[4])])])
    elif a == 4:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])])
    elif a == 3:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])])
    elif a == 2:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])])
    elif a == 1:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])])
    return obj.LineChart()

def plot_TH(year,country):
    conn = sqlite3.connect('./Covid.db')
    if year == 'all':
        query = "SELECT *,SUM([total_case]) AS [total_cases] FROM alldata_province_eng WHERE ([year] = 2021 OR [year] = 2023) OR ([year] = 2022 AND [weeknum] = 52) GROUP BY [province]"
        df = pd.read_sql(query , conn)
        df = df.drop('total_case', axis=1)
        df.rename(columns={"total_cases": "total_case"},inplace = True)
    else:
        query = "SELECT * FROM alldata_province_eng WHERE [year] == %s " % year
        df = pd.read_sql(query , conn)

    alt.data_transformers.disable_max_rows()
    D_country = {1:'ภาคเหนือ',2:'ภาคกลาง',3:'ภาคใต้',4:'ภาคตะวันออก',5:'ภาคตะวันตก',6:'ภาคตะวันออกเฉียงเหนือ'}
    a = len(country)

    obj = ChartManager()
    if a == 6:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])|(df['region'] == D_country[(country[4])])|(df['region'] == D_country[(country[5])])])
    elif a == 5:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])|(df['region'] == D_country[(country[4])])])
    elif a == 4:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])])
    elif a == 3:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])])
    elif a == 2:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])])
    elif a == 1:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])])
    return obj.ThailandTopoChart(500,600)

def plot_country(year,country):
    conn = sqlite3.connect('./Covid.db')
    if year == 'all':
        query = "SELECT *,SUM([total_case]) AS [total_cases] FROM alldata_province_eng WHERE ([year] = 2021 OR [year] = 2023) OR ([year] = 2022 AND [weeknum] = 52) GROUP BY [province]"
        df = pd.read_sql(query , conn)
        df = df.drop('total_case', axis=1)
        df.rename(columns={"total_cases": "total_case"},inplace = True)
    else:
        if year == 2022:
            query = "SELECT * FROM alldata_province_eng WHERE [year] == %s  AND [weeknum] = 52" % year
            df = pd.read_sql(query , conn)
        else:
            query = "SELECT * FROM alldata_province_eng WHERE [year] == %s " % year
            df = pd.read_sql(query , conn)

    alt.data_transformers.disable_max_rows()
    D_country = {1:'ภาคเหนือ',2:'ภาคกลาง',3:'ภาคใต้',4:'ภาคตะวันออก',5:'ภาคตะวันตก',6:'ภาคตะวันออกเฉียงเหนือ'}
    a = len(country)

    obj = ChartManager()
    #if get only one region
    if a == 6:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])|(df['region'] == D_country[(country[4])])|(df['region'] == D_country[(country[5])])])
    elif a == 5:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])|(df['region'] == D_country[(country[4])])])
    elif a == 4:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])|(df['region'] == D_country[(country[3])])])
    elif a == 3:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])|(df['region'] == D_country[(country[2])])])
    elif a == 2:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])|(df['region'] == D_country[(country[1])])])
    elif a == 1:
        obj.setDataframe(df.loc[(df['region'] == 'ทั้งประเทศ')|(df['region'] == D_country[(country[0])])])
    #นี่เป็นตัวอย่างการ query ให้ดูว่า chart จะมีลักษณะเป็นอย่างไร
    #แต่ถ้าของจริงจะต้องใช้ไฟล์ที่ query มาจาก Back-end แล้วนำไฟล์นั้นไปใช้เลย
    return obj.ThailandTopoChart(300,400)


class input(BaseModel):   
    year: list
    area:list

@app.post('/country_graphresult')
async def read_Country_graph(request: input):
    try:
        data = {
            'year': request.year,
            'area': request.area
        }
        if data['year'] == [2021,2022,2023]:
                Result_plot = plot_country('all',data['area'])
        else:
            Result_plot = plot_country(data['year'][0],data['area'])
        Result_plot_json = json.loads(Result_plot)
       
        return Result_plot_json
    
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    
@app.post('/bar_graphresult')
async def plot_barChart(request: input):
    try:
        data = {
            'year': request.year,
            'area': request.area
        }
        if data['year'] == [2021,2022,2023]:
                Result_plot_bar = plot_bar('all',data['area'])
        else:
            Result_plot_bar = plot_bar(data['year'][0],data['area'])

        Result_plot_bar_json = json.loads(Result_plot_bar)

        return Result_plot_bar_json
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
    
@app.post('/line_graphresult')
async def plot_lineChart(request: input):
    try:
        data = {
            'year': request.year,
            'area': request.area
        }
        if data['year'] == [2021,2022,2023]:
                Result_plot_line = plot_line('all',data['area'])
        else:
            Result_plot_line = plot_line(data['year'][0],data['area'])

        Result_plot_line_json = json.loads(Result_plot_line)

        return Result_plot_line_json
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))

@app.get("/")
def read_root():
    return {"Welcome": "Datavisualization Webapp"}

@app.get("/overall")
def get_overall_data():
    try:
        conn = sqlite3.connect('./Covid.db')
        c = conn.cursor()
        c.execute('''select  total_case,total_death,total_recovered  from overall_data where year = 2022 and weeknum=52''')
        data = c.fetchone()
        conn.close()
        return {"totalcase": data[0],"deaths":data[1],"recovered":data[2]}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))