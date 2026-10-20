# Liftoff — System Architecture & Data Integration

## 1. Project Overview

Liftoff is a rocket launch analysis dashboard that combines historical launch data, machine learning predictions, and physics-based trajectory simulations into one interactive application.

The dashboard will be built using Streamlit for the user interface and Plotly for visualizations. Users will be able to select rocket launch parameters, view predicted launch success and delays, and explore simulated rocket trajectories.

The project is divided into three subteams:

- **Data Engineering & ML:** Collects and processes launch data and develops models to predict launch outcomes and delays.
- **Physics & Trajectory Modeling:** Develops physics-based simulations to calculate rocket flight paths.
- **Dashboard & Integration:** Builds the user interface, displays predictions and trajectories, and connects the other subteams' components.

This document describes how these components are expected to communicate. Specific function interfaces will be finalized after coordination with the other subteams.

## 2. End-to-End Data Flow

The Liftoff dashboard uses the following five main stages. The ML inference and physics simulation stages may run independently using shared prepared data, depending on the final integration design.

1. **User Inputs:** The user selects a rocket, launch site, and available launch conditions through the Streamlit interface.
2. **Data Processing:** The data module retrieves and prepares relevant rocket, launch, and weather information for downstream calculations.
3. **ML Inference:** The machine learning module receives prepared features and predicts launch success probability and expected delay hours.
4. **Physics Simulation:** The physics module receives rocket and simulation parameters and calculates a simulated trajectory using physics-based equations.
5. **Visualization:** The dashboard displays model predictions and trajectory results using Plotly charts inside Streamlit.

The ML and Physics modules may use shared prepared data, but the physics simulation does not necessarily depend on the ML prediction. The dashboard is responsible for coordinating these components and presenting their results together.

The exact data fields and function interfaces will be confirmed with the Data Engineering & ML and Physics & Trajectory Modeling subteams.

## 3. Python Module Structure

The Liftoff project organizes its Python code into four main modules inside the `src/` directory. Each module has a separate responsibility to keep the project organized and make integration easier.

- **`src.app`:** Handles the Streamlit user interface, user input controls, and Plotly visualizations. It connects the other modules and displays their results.
- **`src.data`:** Handles collecting, loading, cleaning, and preparing launch, rocket, and weather data for the application and ML models.
- **`src.models`:** Handles machine learning predictions, including launch success probability and expected delay hours.
- **`src.physics`:** Handles physics-based trajectory simulations and produces flight path coordinates for visualization.

### Module Communication

The dashboard will import functions from the data, models, and physics modules instead of duplicating their calculations. The data module will provide prepared inputs to the ML and physics modules as needed. The dashboard will collect the results and display them using Plotly.

The exact Python files and function names inside these modules are still being determined by the respective subteams.

## 4. Function Inputs and Outputs

The following interfaces are proposed for connecting the dashboard with the other project modules. Function names, parameters, and return formats must be confirmed with the responsible subteams before implementation.

### Data Module (`src.data`)

Proposed function: `prepare_launch_data(rocket, launch_site, weather)`

Inputs:
- `rocket`: Selected rocket or rocket family.
- `launch_site`: Selected launch location.
- `weather`: Available weather conditions at launch time.

Output:
- A dictionary or structured record containing cleaned launch information and relevant features for downstream modules.

### Machine Learning Module (`src.models`)

Proposed function: `predict_launch_outcome(features)`

Input:
- `features`: Prepared launch features supplied by the data module.

Output:
- `success_probability`: Predicted probability of launch success, represented as a number between 0 and 1.
- `predicted_delay_hours`: Estimated launch delay in hours.

### Physics Module (`src.physics`)

Proposed function: `simulate_trajectory(parameters)`

Input:
- `parameters`: Simulation settings such as initial velocity, launch angle, and other required physical values.

Output:
- `time`: Simulation timestamps.
- `x`: Horizontal position values.
- `y`: Vertical position values.

The returned arrays should have matching lengths. The proposed standard is seconds for time and meters for horizontal and vertical positions. These units must be confirmed with the Physics subteam before integration.

### Dashboard Module (`src.app`)

The Streamlit application will collect user inputs, call the appropriate data, ML, and physics functions, and display the returned results.

The dashboard will use Plotly to visualize trajectory coordinates and present predicted success probability and delay hours.

### Proposed Python Imports

The dashboard may use imports similar to the following:

```python
from src.data.pipeline import prepare_launch_data
from src.models.inference import predict_launch_outcome
from src.physics.solver import simulate_trajectory
```

These file paths are proposed examples. The corresponding Python files and functions have not yet been confirmed or implemented.

### Interface Status

These are proposed integration contracts, not confirmed implementations. The Data Engineering & ML and Physics & Trajectory Modeling leads will confirm the actual function names, required parameters, return types, and units before the interfaces are finalized.

## 5. Integration Rules and Error Handling

To keep the Liftoff application organized and reliable, the following integration rules are proposed.

### Integration Rules

1. Each subteam will maintain its code inside its assigned module under `src/`.
2. The dashboard will import functions from the data, models, and physics modules rather than duplicating their logic.
3. Functions should use clearly defined inputs and outputs so that modules can communicate consistently.
4. Shared data formats and measurement units should be documented and agreed upon before integration.
5. Changes to shared function interfaces should be communicated to the Dashboard & Integration team before implementation.
6. The dashboard should display ML predictions and physics simulations separately when one component does not depend on the other.

### Error Handling

The dashboard should handle common problems without crashing the entire application.

- **Missing user inputs:** Display a message asking the user to complete the required fields.
- **Unavailable data:** Notify the user when launch or weather information cannot be retrieved.
- **ML prediction errors:** Display a warning when predictions are unavailable instead of showing incorrect results.
- **Physics simulation errors:** Display a warning when the simulation cannot run or returns invalid coordinates.
- **Invalid values:** Check required inputs and expected output formats before using them in calculations or visualizations.

These rules describe expected application behavior and will be refined as the subteams implement their components.

## 6. Cross-Team Dependencies

The Dashboard & Integration subteam is responsible for connecting the work produced by the Data Engineering & ML and Physics & Trajectory Modeling subteams.

### Data Engineering & ML Dependencies

The dashboard team needs the following information from the Data Engineering & ML subteam:

- The Python module and function names used to prepare launch data and generate predictions.
- The required input features for the machine learning models.
- The format and data types of the prediction outputs.
- How missing data and unavailable predictions will be handled.

### Physics & Trajectory Modeling Dependencies

The dashboard team needs the following information from the Physics & Trajectory Modeling subteam:

- The Python module and function names used to run trajectory simulations.
- The required simulation inputs and their measurement units.
- The format of the returned trajectory coordinates and timestamps.
- Any limitations or assumptions that the dashboard should communicate to users.

### Dashboard & Integration Responsibilities

The Dashboard & Integration subteam will:

- Build the Streamlit interface and user input controls.
- Connect the data, machine learning, and physics modules to the dashboard.
- Display predictions and trajectory results using Plotly.
- Validate incoming results before displaying them.
- Coordinate interface changes with the other subteams.

### Pending Confirmations

The proposed function interfaces in Section 4 are awaiting confirmation from the Data Engineering & ML and Physics & Trajectory Modeling leads. Once their implementations and data formats are finalized, this document will be updated to reflect the agreed-upon integration contracts.

Until then, the proposed interfaces should be treated as planning guidelines rather than completed or verified implementations.


