import simpy
import random
import pandas as pd
import numpy as np

class default_params():
    run_name = 'default'
    run_time = 52
    #Referrals
    internal = 10
    external = 20
    #ROTs per week
    ROT_rate = 0.03
    #Appointments per week
    default_apts = 20
    #Create some randomness for testing (this cannot be list comprehension as
    #causes errors due to scope)
    arr_and_apts = pd.DataFrame({'Internal':[internal] * run_time,
                           'External':[external] * run_time,
                           'Appointments':[default_apts] * run_time})
    #apts = []
    #for i in range(run_time):
    #    apts.append(default_apts + random.randint(-10, 20))
    #new_apts = pd.DataFrame({'Apts':apts}, index=[i for i in range(run_time)])
    #DNA Rate
    DNA_rate = 0.05
    #Clinical Priority Split
    prior1 = 0.15
    prior2 = 0.35
    prior3 = 0.50
    clin_prior = pd.DataFrame({'Priority':[i+1 for i in range(3)],
                               'Percent' :[prior1, prior2, prior3]})
    #Exit Probabilities
    disch = 40
    FUapt = 30 # goes on into FU model
    treat = 30 # goes on into thetre day case model
    #Lists for results
    pat_res = []
    occ_res = []

class spawn_patient:
    def __init__(self, p_id, ROT_rate, DNA_rate, clin_prior, disch, FUapt, treat, time, run_time):
        #patient id
        self.id = p_id
        #referal type
        self.referal_type = np.nan
        #ROT
        self.ROT = random.random() < ROT_rate
        self.ROT_week = (random.randint(time, run_time)
                         if self.ROT else np.nan)
        #DNA
        self.DNA = random.random() < DNA_rate
        self.DNA_week = np.nan
        #Clinical Priority
        self.priority = random.choices(clin_prior['Priority'],
                                       clin_prior['Percent'])[0]
        #Wait start
        self.wait_start = np.nan
        #seen time
        self.seen_week = np.nan
        #Exit method
        self.exit = (random.choices(['Discharge', 'Follow Up', 'Treatment'],
                                   [disch, FUapt, treat])[0]
                                   if not self.ROT else 'Discharge')
        #Request
        self.request = np.nan


class wait_list_model:
    def __init__(self, input_params):#self, run_number, input_params):
        #Set up lists to record results
        self.patient_results = []
        self.occupancy_results = []
        #start environment, set patient counter to 0 and set run number
        self.env = simpy.Environment()
        self.input_params = input_params
        self.patient_counter = 0
        #self.run_number = run_number
        #establish resources
        self.priority_screen = simpy.PriorityResource(self.env, capacity=1)
        self.new_outpat = simpy.Store(self.env, capacity=float('inf'))

    def replenish_appointments(self):
        #Function to put new appointments into the store
        while True:
            #Get the number of remaining appointments and the number of apts
            #for next week.  Replenish up to this figure
            remains = len(self.new_outpat.items)
            no_apts = self.input_params.arr_and_apts.loc[self.env.now, 'Appointments']
            print(f' XX {remains} appointments left, next week has {no_apts}')
            new_apts = no_apts - remains
            if new_apts > 0:
                print(f'Adding {new_apts} new appointments to reach {no_apts}')
                for _ in range(new_apts):
                    yield self.new_outpat.put('resource')
            else:
                print(f'Removing {new_apts} appointments to reach {no_apts}')
                for _ in range(abs(new_apts)):
                    yield self.new_outpat.get()
            yield self.env.timeout(1)

    ###########################ARRIVALS##################################
    def internal_referrals(self):
        while True:
            #Spawn in the number of internal referrals for that week
            arr = self.input_params.arr_and_apts.loc[self.env.now, 'Internal']
            for _ in range(arr):
                self.patient_counter += 1
                print(f'Spawning patient {self.patient_counter} from internal referal at {self.env.now}')
                p = spawn_patient(self.patient_counter,
                                  self.input_params.ROT_rate,
                                  self.input_params.DNA_rate,
                                  self.input_params.clin_prior,
                                  self.input_params.disch,
                                  self.input_params.FUapt,
                                  self.input_params.treat,
                                  self.env.now+1,
                                  self.input_params.run_time)
                p.referal_type = 'Internal'
                p.wait_start = self.env.now
                #p.ROT_week = random.randint(self.env.now+1, self.input_params.run_time)
                #begin wait list process
                self.env.process(self.wait_list(p))
            #Wait 1 until next week, then spawn again
            yield self.env.timeout(1)

    def external_referrals(self):
        while True:
            #Spawn in the number of external referrals for that week
            arr = self.input_params.arr_and_apts.loc[self.env.now, 'External']
            for _ in range(arr):
                self.patient_counter += 1
                print(f'Spawning patient {self.patient_counter} from external referal at {self.env.now}')
                p = spawn_patient(self.patient_counter,
                                  self.input_params.ROT_rate,
                                  self.input_params.DNA_rate,
                                  self.input_params.clin_prior,
                                  self.input_params.disch,
                                  self.input_params.FUapt,
                                  self.input_params.treat,
                                  self.env.now+1,
                                  self.input_params.run_time)
                p.referal_type = 'External'
                p.wait_start = self.env.now
                #p.ROT_week = random.randint(self.env.now+1, self.input_params.run_time)
                #begin wait list process
                self.env.process(self.wait_list(p))
            #Wait 1 until next week, then spawn again
            yield self.env.timeout(1)
    
    ######################## WAIT LIST JOURNEY #############################

    def wait_list(self, patient):
        #Store patient results so we still have a record of those who are still waiting
        self.store_patient_results(patient)
        print(f'patient {patient.id} requesting appointment at {self.env.now} with priority {patient.priority}')
        with self.priority_screen.request(priority=patient.priority) as req:
            #request priority resource
            yield req
            print(f'patient {patient.id} at front of queue at {self.env.now}')
            #If patient doesn't ROT, then they take an appointment
            if not patient.ROT:
                yield self.new_outpat.get()
                print(f'patient {patient.id} seen at {self.env.now}')
                patient.seen_week = self.env.now
            else:
                print(f'patient {patient.id} at front of queue at {self.env.now} and is ROT')
                patient.ROT_week = self.env.now

        #If patient was DNA, they didn't use their appointment, so they queue again
        if patient.DNA:
            yield self.env.timeout(1)
            print(f'patient {patient.id} DNA - requesting 2nd appointment at {self.env.now} with priority {patient.priority}')
            with self.priority_screen.request(priority=patient.priority) as req:
                #request priority resource
                yield req
                print(f'patient {patient.id} at front of queue at {self.env.now}')
                #Once they have the resource, take an appointment from the store
                yield self.new_outpat.get()
                patient.DNA_week = self.env.now

        #Patient leave method
        if patient.exit == 'Discharge':
            print(f'patient {patient.id} discharged and removed from wait list')
        elif patient.exit == 'Follow Up':
            print(f'patient {patient.id} requres follow up apt, put on FU wait list')
        elif patient.exit == 'Treatment':
            print(f'patient {patient.id} requres treatment, put on day case list')
        #record patient results
        self.store_patient_results(patient)

###################RECORD RESULTS####################
    def store_patient_results(self, patient):
        self.patient_results.append([patient.id,
                                     patient.referal_type,
                                     patient.ROT,
                                     patient.DNA,
                                     patient.priority,
                                     patient.wait_start,
                                     patient.seen_week,
                                     patient.ROT_week,
                                     patient.DNA_week,
                                     patient.exit])
    
    def store_occupancy(self):
        while True:
            self.occupancy_results.append([self.priority_screen._env.now,
                                           len(self.priority_screen.queue),
                                           self.input_params.arr_and_apts.loc[self.env.now, 'Appointments'],
                                           len(self.new_outpat.items)])
            yield self.env.timeout(1)

########################RUN#######################
    def run(self):
        self.env.process(self.replenish_appointments())
        self.env.process(self.internal_referrals())
        self.env.process(self.external_referrals())
        self.env.process(self.store_occupancy())
        self.env.run(until = self.input_params.run_time)
        return self.patient_results, self.occupancy_results


def export_results(pat_results, occ_results):
    ####################Patient Table
    patient_df = pd.DataFrame(pat_results, columns=['Patient ID',
                                           'Referal Type', 'ROT', 'DNA',
                                           'Priority', 'Week Start',
                                           'Week Seen', 'ROT Week', 'DNA Week', 'Exit']
                             ).drop_duplicates(subset='Patient ID', keep='last')
    patient_df['LoW'] = patient_df['Week Seen'].fillna(52) - patient_df['Week Start']
    patient_df.loc[patient_df['ROT'], 'LoW'] = np.nan
    ####################Occupancy Table
    occupancy_df = pd.DataFrame(occ_results, columns=['Time', 'Queue Length',
                                                     'Apts Added', 'Apts Left'])
    return patient_df, occupancy_df

def run_the_model(input_params):
    #run the model for the number of iterations specified
    #for run in range(input_params.iterations):
    model = wait_list_model(input_params)
    patient, occ = model.run()
    patient_df, occ_df = export_results(patient, occ)
    return patient_df, occ_df

###############################################################################
#Run and save results
pat, occ = run_the_model(default_params)
x=4