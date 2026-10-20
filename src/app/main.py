# placeholder for streamlit connection
import streamlit as st

col1, col2, col3 = st.columns(3)

with col1:
    with st.sidebar:
        st.subheader("Rocket Selection: ")
        #made placeholder selections
        rocket = st.selectbox("Select Rocket: ", ["Rocket a" , "Rocket b", "Rocket c"])

        st.subheader("Payload Mass Slider: ")
        #made a slider for payload mass, min and max value can be edited later
        mass = st.slider("Payload Mass: ", min_value = 10, max_value = 1000)

        #made placeholder selections for weather
        st.subheader("Weather Condition Overrides: ")
        weather = st.selectbox("Select Weather Condition", ["option a", "option b", "option c"])

        #not sure if this is something that would be added but I can change it
        st.subheader("Fuel")
        fuel = st.slider("Fuel Amount: ", min_value = 0, max_value = 100)

with col2:
    with st.container(border = True):
        #this is where the graphs will be placed for now
        st.metric("Placeholder", 0)
        placeholder1 = st.empty()

with col3:
    with st.container(border = True):
        #made another placeholder
        st.metric("Placeholder", 0)
        placeholder2 = st.empty()



