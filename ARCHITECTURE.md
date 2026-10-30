
# Liftoff — System Architecture & Data Integration

## Streamlit Session State Management (Issue 18)

### Purpose

The dashboard uses Streamlit's `st.session_state` to preserve user selections and calculated results when users interact with the application or switch between tabs.

### Module Location

`src/app/state.py`

This module manages shared session state for the dashboard.

### Session State Keys

| Key | Default Value | Description |
|---|---|---|
| `selected_rocket` | `None` | Stores the user's selected rocket. |
| `payload_mass` | `0.0` | Stores the payload mass. |
| `wind_speed` | `0.0` | Stores the selected wind speed. |
| `trajectory_data` | `None` | Stores calculated trajectory results. |

### Integration With Dashboard Components

Dashboard components should import the state initialization function from `src.app.state` and initialize session state before accessing shared values.

User input controls should update the corresponding session state keys. Trajectory visualizations should read `trajectory_data` to display calculated results.

### Data Flow

1. The user selects rocket parameters in the Streamlit dashboard.
2. The application saves these values in `st.session_state`.
3. The physics module uses the selected parameters to calculate trajectory data.
4. The application stores the resulting trajectory data in `st.session_state["trajectory_data"]`.
5. Plotly visualizations read the stored data and display the trajectory.
6. Switching between tabs preserves the stored values within the same Streamlit session.

### Error Handling

Session state keys should be initialized before use to prevent missing-key errors. The dashboard should check whether trajectory data is available before attempting to display charts.

The final component import paths and integration behavior will be verified as the dashboard modules are implemented.

