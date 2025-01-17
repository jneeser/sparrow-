import heatflux
import standard_fluid_config as std
import pressuredrop 

import numpy as np
import thermo
import rocketcea
from matplotlib import pyplot as plt
import csv
import scipy.optimize
from scipy import interpolate
import time


# coolant properties 
fuel_composition = ['C2H5OH']
fuel_mass_fraction = [1]
number_of_channels = 42*2
wall_thickness_tbc = 0.1e-3
thermal_conductivity = 24							# Inconel at 800 C
thermal_conductivity_tbc = 0.8

# create initial objects 
geometry = np.genfromtxt('sparrow_contour_1_5.txt', delimiter='', dtype=None, skip_header = 13) / 1000 					# conversion to [m]
isnetropic = heatflux.Isentropic(std.chamber_pressure, std.cea.T_static, std.cea.gamma)
mach = isnetropic.mach(geometry)
t_aw = isnetropic.adiabatic_wall_temp(mach, geometry, std.cea.Pr)

heat = heatflux.Heattransfer(fuel_composition, fuel_mass_fraction, std.fuel_massflow, std.total_massflow, std.cea, std.chamber_pressure, std.fuel_temperature, std.fuel_inlet_pressure, geometry, number_of_channels, thermal_conductivity, thermal_conductivity_tbc, wall_thickness_tbc)

y_coordinates = geometry[:,1][::-1]
x_coordinates = geometry[:,0][::-1]

###############################
# starting the section iterator 
###############################

tol = 1e-2 							# acceptable temeprature difference 
max_iter = 100

# empty output arrays for pressuredrop.py output
fi_arr = np.ndarray(len(y_coordinates))
dp_arr = np.ndarray(len(y_coordinates))
vi_arr = np.ndarray(len(y_coordinates))
Rei_arr = np.ndarray(len(y_coordinates))
dhi_arr = np.ndarray(len(y_coordinates))
dho_arr = np.ndarray(len(y_coordinates))
vo_arr = np.ndarray(len(y_coordinates))
Reo_arr = np.ndarray(len(y_coordinates))
hi_arr = np.ndarray(len(y_coordinates))
ho_arr = np.ndarray(len(y_coordinates))
wt1_arr = np.ndarray(len(y_coordinates))
rf1i_arr = np.ndarray(len(y_coordinates))
rf1o_arr = np.ndarray(len(y_coordinates))
rf2_arr = np.ndarray(len(y_coordinates))
wto_arr = np.ndarray(len(y_coordinates))
t_arr = np.ndarray(len(y_coordinates))
stress_ratio_arr = np.ndarray(len(y_coordinates))

# empty arrays for heatflux outputs 
wall_t_arr = np.ndarray(len(y_coordinates))
tbc_t_arr = np.ndarray(len(y_coordinates))
coolant_t_arr = np.ndarray(len(y_coordinates))
coolant_p_arr = np.ndarray(len(y_coordinates))
q_total_arr = np.ndarray(len(y_coordinates))
q_rad_arr = np.ndarray(len(y_coordinates))
halpha_gas_arr = np.ndarray(len(y_coordinates))
sec_length_arr = np.ndarray(len(y_coordinates))

# material 
E_in718 = [199947961502.171,198569010043.535,195811107126.264,193053204208.992,190295301291.721,186847922645.132,184090019727.861,180642641081.271,177884738164,174437359517.411,170989980870.822,166853126494.915,163405747848.326,158579417743.101,153753087637.876,146858330344.698,139274097322.202,129621437111.752,119968776901.302,109626640961.535,98595029292.4497]
T1_in718 = [294.3,310.9,366.5,422,477.6,533.2,588.7,644.3,699.8,755.4,810.9,866.5,922,977.6,1033.2,1088.7,1144.3,1199.8,1255.4,1310.9,1366.5]
sig_in718 = [1123.85e6,1075.58e6,1020.42e6,965.27e6,930.79e6,799.79e6,689.48e6]
T2_in718 = [293,588.7,810.9,922,977.6,1033.2,1088.7]
in718 = pressuredrop.metal(E=(E_in718,T1_in718),k=thermal_conductivity,v=0.29,alpha=12e-6,sig_yield=(sig_in718, T2_in718))
#alu = pressuredrop.metal(E=57e9,k=thermal_conductivity,v=0.33,alpha=21e-6,sig_yield=([180e6,180e6,175e6,155e6,140,85,50,25,0],[293,403,453,493,523,573,623,673,753]))


# initial guess
cool_side_wall_temp = 400
wall_temperature = 400
coolant_temp = 400
radiation = 0
coolant_pressure = 80e5
heat.P_local = 50e5
halpha = 3000
t = 2e-3
wt1 = 0.6e-3
wt2 = 0.6e-3
rf1 = 0.1e-3
rf2 = 0.1e-3

t1 = time.time()
# optimisation 
for i in range(len(y_coordinates)):

	if i == 0:
		section_length = 0
	else:
		section_length = np.sqrt((x_coordinates[i] - x_coordinates[i-1])**2 + (y_coordinates[i]-y_coordinates[i-1])**2)
	
	# iteration parameters 
	iteration = 0
	difference = 1

	while difference > tol:
		initial_params = pressuredrop.parameters(ri=y_coordinates[i],t=t,wt1=wt1,wt2=wt2,rf1=rf1,rf2=rf2,N=np.round(number_of_channels/2,0))
		initial_heat = pressuredrop.sim(wall_temperature, t_aw[i], heat.coolant.T, halpha, radiation, coolant_pressure, heat.P_local, y_coordinates[i], thermal_conductivity_tbc, wall_thickness_tbc)
		try:
			new_params = pressuredrop.physics(initial_params,in718,initial_heat,heat.coolant)
		except:
			print('skipped iteration: ', iteration, ' due to infeasible solution')
			pass

		avg_hydrolic_diameter = (new_params.dhi + new_params.dho) / 2 
		wall_thickness = new_params.par.wt1

		heat_flux, new_wall_temp, cool_side_wall_temp, tbc_wall_temp, Re, Nu, radiation, halpha = heat.iterator(y_coordinates[i], avg_hydrolic_diameter, section_length, wall_thickness, mach[i], t_aw[i])

		difference = abs(new_wall_temp - wall_temperature)

		iteration += 1
		print('section: ', i, ' sub-iteration: ', iteration, ':')
		print('	temperature difference: ', difference)
		print('	max wall temperature: ', round(wall_temperature,2))
		print('	stress ratio: ', round(new_params.sigma_rat,2))

		if iteration > max_iter:
			raise ValueError('Non-convergence, iteration number exceeded ', max_iter)
			
		# Update initial guess
		wall_temperature = new_wall_temp	
		wt1 = new_params.par.wt1
		rf1 = new_params.par.rf1i
		rf2 = new_params.par.rf2
		t = new_params.par.t
		wt2 = new_params.par.wt2

		if iteration > 10:
			print("not converged after 10 iterations, moving to section: ", i+1)
			break

	T_new = heat.coolant.T + heat_flux*2*np.pi*y_coordinates[i]*section_length / (heat.coolant_massflow*heat.coolant.Cp) 
	heat.coolant.calculate(P=heat.coolant.P, T=T_new)
	coolant_pressure -= new_params.dp*section_length


	# updating arrays 
	fi_arr[i] = new_params.fi
	dp_arr[i] = new_params.dp
	vi_arr[i] = new_params.vi
	Rei_arr[i] = new_params.Rei
	dhi_arr[i] = new_params.dhi
	dho_arr[i] = new_params.dho
	vo_arr[i] = new_params.vo
	Reo_arr[i] = new_params.Reo
	hi_arr[i] = new_params.hi
	ho_arr[i] = new_params.ho
	wt1_arr[i] = new_params.par.wt1
	rf1i_arr[i] = new_params.par.rf1i
	rf1o_arr[i] = new_params.par.rf1o
	rf2_arr[i] = new_params.par.rf2
	wto_arr[i] = new_params.wto
	t_arr[i] = new_params.par.t
	stress_ratio_arr[i] = new_params.sigma_rat

	# empty arrays for heatflux outputs 
	wall_t_arr[i] = wall_temperature
	coolant_t_arr[i] = T_new
	q_total_arr[i] = heat_flux
	q_rad_arr[i] = radiation
	halpha_gas_arr[i] = halpha
	sec_length_arr[i] = section_length
	tbc_t_arr[i] = tbc_wall_temp

t2 = time.time()
print('optimisation runtime: ', t2-t1, '[s]')

with open('optimised_geometry.csv', 'w', newline='') as file:
	writer = csv.writer(file)
	writer.writerow(["x coordinate","y_coordinate","gas heat transfer coefficient", "heat flux", "max wall temperature", "tbc wall temperature", "Re inner", "Re outer", "pressure drops", "section lenghts","hydrolic diameter inner",
					 "hydrolic diameter outer", "wt1", "wto", "rf1 inner", "rf1 outer", "rf2", "t", "hi", "ho", "stress ratios"]
	)
	for i in range(len(geometry[:,1])):
		idx = len(geometry[:,1]) - i - 1
		writer.writerow([geometry[i,0], geometry[i,1], halpha_gas_arr[idx], q_total_arr[idx], wall_t_arr[idx], tbc_t_arr[idx], Rei_arr[idx], Reo_arr[idx], dp_arr[idx], sec_length_arr[idx], dhi_arr[idx],
						dho_arr[idx], wt1_arr[idx], wto_arr[idx], rf1i_arr[idx], rf1o_arr[idx], rf2_arr[idx], t_arr[idx], hi_arr[idx], ho_arr[idx], stress_ratio_arr[idx]
		])

