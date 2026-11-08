import time

import streamlit as st

tab1, tab2, tab3 = st.tabs(["Flight Simulation", "ML Analytics", "Telemetry Comparison"])
#code for the sidebar
with st.sidebar.expander("Rocket Configuration"):
        st.subheader("Rocket Selection: ")
        #made placeholder selections
        rocket = st.selectbox("Select Rocket: ", ["Rocket a" , "Rocket b", "Rocket c"])


        st.subheader("Payload Mass Slider: ")
        #made a slider for payload mass, min and max value can be edited later
        mass = st.slider("Payload Mass (kg): ", min_value = 10, max_value = 1000)

with st.sidebar.expander("Weather and Environment"):
        st.subheader("Weather Condition Overrides: ")
        weather = st.selectbox("Select Weather Condition:", ["option a", "option b", "option c"])

        #numerical input for wind speed
        st.subheader("Wind Speed: ")
        wind_speed = st.number_input("Enter Wind Speed: ")

        st.subheader("Launch Site Selection:")
        launch_site = st.selectbox("Select Launch Site:", ["Site A", "Site B", "Site C"])

with st.sidebar:
     st.subheader("Launch!")
     button = st.button("Launch Rocket")

if button:
    with st.spinner("Processing Launch..."):
        time.sleep(5) #simulate the processing time

        if (wind_speed < 0 or wind_speed > 100):
            st.error("Wind speed must be between 0 and 100.")

input_data = {
    "rocket": rocket,
    "mass": mass,
    "weather": weather,
    "wind": wind_speed,
    "launch_site": launch_site
}
#Flight simulation tab
with tab1:
    st.subheader("Flight Simulation")
    st.write("This section will contain the flight simulation graphs and data.")
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border = True):
            #this is where the graphs will be placed for now
            st.metric(label = "Max Altitude (m)", value = 0, delta = 0) #using placeholder values for now


    with col2:
        with st.container(border = True):
            #made another placeholder
            st.metric(label = "Max Velocity (m/s)", value = 0, delta = 0) #using placeholder values for now

    with col3:
        with st.container(border = True):
            #made another placeholder
            st.metric(label = "Flight time", value = 0, delta = 0) #using placeholder values for now
#ML analytics tab
with tab2:
    st.subheader("ML Analytics")
    st.write("This section will contain machine learning analytics related to the flight simulation.")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border = True):
            #this is where the graphs will be placed for now
            st.metric(label = "Model R^2 Score", value = 0, delta = 0) #using placeholder values for now
    
    with col2:
        with st.container(border = True):
            #made another placeholder
            st.metric(label = "Mean Absolute Error", value = 0, delta = 0) #using placeholder values for now
 
#Telemetry comparison tab
with tab3:
    st.subheader("Telemetry Comparison")
    st.write("This section will allow users to compare telemetry data from different flight simulations.")
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border = True):
            #this is where the graphs will be placed for now
            st.metric(label = "Sim vs Real Deviation", value = 0, delta = 0)
            placeholder1 = st.empty()
    
    with col2:
        with st.container(border = True):
            #made another placeholder
            st.metric(label = "Sample Drift", value = 0, delta = 0)
            placeholder2 = st.empty()