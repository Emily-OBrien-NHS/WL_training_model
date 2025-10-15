import streamlit as st
from streamlit import session_state as ss
from wait_list_model import run_the_model, default_params
import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import time

st.set_page_config(
     page_title="Wait List Model",
     page_icon="🏥",
     layout="wide",
     initial_sidebar_state="expanded",
     menu_items={
         'About': "Model to simulate waiting lists"
     }
 )

st.title('Wait List Model')
st.write('''Sliders to adjust input parameters are on the left. 
         Press Run Multiprocess Simulation to run the model, this is the fastest
         run time possible, but may cause an error.  If an error does occur,
         the run model (slow) button should run the model without these erros,
         but will be much slower.''')

with st.sidebar:
    st.markdown('# Input Parameters')
    st.divider()
    st.markdown('# Arrivals')
    internal = st.number_input(label='Internal Referals per week',
                    value=default_params.internal)
    external = st.number_input(label='External Referals per week',
                    value=default_params.external)
    st.divider()
    st.markdown('# Appointments')
    default_apts = st.number_input(label='Number of Appointments Available per week',
                    value=default_params.default_apts)
    st.divider()
    st.markdown('# ROT and DNA')
    ROT_rate = st.slider('ROT Rate', 0.0, 1.0, value=default_params.ROT_rate)
    DNA_rate = st.slider('DNA Rate', 0.0, 1.0, value=default_params.DNA_rate)
    st.divider()
    st.markdown('# Clinical Priority Distribution')
    st.markdown('Values will adjust to ensure they sum to 100%')
    TOTAL = 100
    def update(last):
        change = ss.High + ss.Mid + ss.Low - TOTAL
        sliders = ['High','Mid','Low']    
        last = sliders.index(last)
        ss[sliders[(last+1)%3]] -= np.ceil(change/2)
        ss[sliders[(last+2)%3]] -= np.floor(change/2)
    prior1 = st.number_input('High', key='High', min_value=0, max_value=100, value = 15, on_change=update, args=('High',))
    prior2 = st.number_input('Mid', key='Mid', min_value=0, max_value=100, value = 35, on_change=update, args=('Mid',))
    prior3 = st.number_input('Low', key='Low', min_value=0, max_value=100, value = 50, on_change=update, args=('Low',))

    st.divider()
    st.markdown('# Discharges')
    st.markdown('Values will adjust to ensure they sum to 100%')
    def update(last):
        change = ss.Discharged + ss['Follow Up'] + ss.Treatment - TOTAL
        sliders = ['Discharged','Follow Up','Treatment']    
        last = sliders.index(last)
        ss[sliders[(last+1)%3]] -= np.ceil(change/2)
        ss[sliders[(last+2)%3]] -= np.floor(change/2)
    disch = st.number_input('Discharged', key='Discharged', min_value=0, max_value=100, value = 50, on_change=update, args=('Discharged',))
    FUapt = st.number_input('Follow Up', key='Follow Up', min_value=0, max_value=100, value = 25, on_change=update, args=('Follow Up',))
    treat = st.number_input('Treatment', key='Treatment', min_value=0, max_value=100, value = 25, on_change=update, args=('Treatment',))

st.markdown('# Week by Week Arrivals and Apointments Input')
arr_and_apts = st.data_editor(pd.DataFrame({'Internal':[internal] * default_params.run_time,
                           'External':[external] * default_params.run_time,
                           'Appointments':[default_apts] * default_params.run_time}).T)
fig, ax = plt.subplots(figsize=(20, 2.5))
arr_and_apts.T.plot(ax=ax)
ax.set_xlabel('Week')
ax.set_ylabel('Input')
st.pyplot(fig)

#Get the parameters in a usable format
args = default_params()
#update defaults to selections
args.run_name = 'streamlit'
args.internal = internal
args.external = external
args.default_apts = default_apts
args.arr_and_apts = arr_and_apts.T.reset_index(drop=True).fillna(0)
args.ROT_rate = ROT_rate
args.DNA_rate = DNA_rate
args.clin_prior = pd.DataFrame({'Priority':[i+1 for i in range(3)],
                                'Percent' :[prior1, prior2, prior3]})
args.disch = disch
args.FUapt = FUapt
args.treat = treat

def streamlit_results(pat, occ, run_time):
    #LoW histograms
    st.subheader('Lengt of Wait distribution of those seen:')
    f, (ax1, ax2) = plt.subplots(1, 2, sharey=True, figsize=(20, 2.5))
    pat.loc[~pat['Week Seen'].isna(), 'LoW'].hist(bins=default_params.run_time, ax=ax1, density=True)
    ax1.set_title('Patients Seen')
    ax1.set_xlabel('Weeks Wait')
    pat.loc[pat['Week Seen'].isna(), 'LoW'].hist(bins=default_params.run_time, ax=ax2, density=True)
    ax2.set_title('Patients Waiting to be Seen')
    ax2.set_xlabel('Weeks Wait')
    st.pyplot(f)

    #LoW by priority
    st.subheader('Lengt of Wait distribution by Patient priority:')
    f, (ax1, ax2, ax3) = plt.subplots(1, 3, sharey=True, figsize=(20, 2.5))
    pat.loc[pat['Priority'] == 1, 'LoW'].hist(bins=default_params.run_time, ax=ax1, density=True)
    ax1.set_title('High Priority')
    ax1.set_xlabel('Weeks Wait')
    pat.loc[pat['Priority'] == 2, 'LoW'].hist(bins=default_params.run_time, ax=ax2, density=True)
    ax2.set_title('Medium Priority')
    ax2.set_xlabel('Weeks Wait')
    pat.loc[pat['Priority'] == 3, 'LoW'].hist(bins=default_params.run_time, ax=ax3, density=True)
    ax3.set_title('Low Priority')
    ax3.set_xlabel('Weeks Wait')
    st.pyplot(f)

    #Queue and appts plots
    st.subheader('Queue length and number of appointments:')
    occ = (occ
           .join(pat.loc[pat['ROT']].groupby('ROT Week')['Patient ID'].count().rename('ROT'))
           .join(pat['DNA Week'].value_counts().rename('DNA'))).fillna(0)
    # Create 2x2 sub plots
    gs = gridspec.GridSpec(2, 2)
    fig = plt.figure(figsize=(20, 6))
    #ROT and DNA
    ax1 = fig.add_subplot(gs[0, 0]) 
    occ[['ROT', 'DNA']].plot(ax=ax1)
    ax1.set_title('ROT and DNA')
    #Appointments
    ax2 = fig.add_subplot(gs[0, 1])
    occ[['Apts Added', 'Apts Left']].rename(columns={'Apts Left':'Apts Remaining'}).plot(ax=ax2)
    ax2.set_title('Appointments')
    #Wait List
    ax3 = fig.add_subplot(gs[1, :]) 
    occ['Queue Length'].plot(ax=ax3)
    ax3.set_title('Wait List')
    st.pyplot(fig)

    #Discharge locations
    st.subheader('Exit Methods over time:')
    fig, ax = plt.subplots(figsize=(20, 2.5))
    pat.groupby(['Week Seen', 'Exit'], as_index=False)['Patient ID'].count().pivot(index='Week Seen', columns='Exit', values='Patient ID').plot(ax=ax)
    ax.set_title('Exit Method by Model Week')
    st.pyplot(fig)

#Button to run simulation
if st.button('Run Model'):
    st.subheader('Simulation Progress:')
    with st.empty():
        t0 = time.time()
        with st.spinner('Simulating patient arrivals and discharges...'):
            pat, occ = run_the_model(args)
        t1 = time.time()
        run_time = t1-t0
    st.success('Done!')
    streamlit_results(pat, occ, run_time)


