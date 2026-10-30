import streamlit as st

col1, col2 = st.columns(2)


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

input_data = {
    "rocket": rocket,
    "mass": mass,
    "weather": weather,
    "wind": wind_speed,
}

with col1:
    with st.container(border = True):
        #this is where the graphs will be placed for now
        st.metric("Placeholder", 0)
        placeholder1 = st.empty()

with col2:
    with st.container(border = True):
        #made another placeholder
        st.metric("Placeholder", 0)
        placeholder2 = st.empty()

