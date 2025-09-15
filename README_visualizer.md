# Real-time Radar Visualizer

This script provides real-time visualization of point cloud and height data from the xWR6843 radar sensor.

## Features

- **3D Point Cloud Visualization**: Real-time 3D scatter plot of detected points with color-coding by height
- **Height Data Display**: Bar chart showing track heights for each detected person/object
- **Top-down View**: X-Y plane view for spatial awareness
- **System Information Panel**: Real-time statistics and track information
- **Persistent Display**: Shows recent frames with fading effect for better tracking
- **Automatic COM Port Detection**: Auto-detects radar COM ports on Windows and Linux

## Installation

1. Install required dependencies:
```bash
pip install -r requirements_visualizer.txt
```

2. Ensure you have the following files in the same directory:
   - `realtime_visualizer.py`
   - `datastream.py`
   - `parseFrame.py`
   - `parseTLVs.py`
   - `tlv_defines.py`
   - `gui_common.py`
   - `Final_config_6m.cfg` (or your radar configuration file)

## Usage

### Basic Usage
```bash
python realtime_visualizer.py
```

The script will:
1. Auto-detect COM ports (Windows/Linux)
2. Connect to the radar
3. Configure the radar with the default config file
4. Start real-time visualization

### Manual COM Port Specification
If auto-detection fails, you'll be prompted to enter COM ports manually.

### Configuration File
By default, the script uses `Final_config_6m.cfg`. You can modify the `configure_radar()` call in the `main()` function to use a different config file.

## Visualization Layout

The visualization window contains four panels:

1. **Top-left: 3D Point Cloud**
   - Shows detected points in 3D space
   - Points are colored by height (Z-coordinate)
   - Tracked objects shown as red markers with track IDs
   - Recent frames shown with fading effect

2. **Top-right: Track Heights**
   - Bar chart of height data for each tracked object
   - Height values displayed on top of bars
   - Updates in real-time as objects are tracked

3. **Bottom-left: Top-down View**
   - X-Y plane view of the detection area
   - Shows spatial distribution of points and tracks
   - Useful for understanding movement patterns

4. **Bottom-right: System Information**
   - Frame number and timing information
   - Number of detected points and tracks
   - Individual track height information
   - Current timestamp

## Controls

- **Close Window**: Stop visualization
- **Ctrl+C**: Emergency stop from terminal

## Customization

You can customize the visualizer by modifying parameters in the `RealtimeRadarVisualizer` constructor:

```python
visualizer = RealtimeRadarVisualizer(
    max_points=1000,      # Maximum points to display
    history_length=30     # Number of frames to keep in history
)
```

### Adjusting Plot Limits
Modify the axis limits in the `setup_plots()` method to match your detection area:

```python
self.ax_3d.set_xlim([-3, 3])    # X range in meters
self.ax_3d.set_ylim([0, 6])     # Y range in meters  
self.ax_3d.set_zlim([0, 3])     # Z range in meters
```

## Troubleshooting

### COM Port Issues
- **Windows**: Ensure the radar is connected and drivers are installed
- **Linux**: You may need to add your user to the `dialout` group:
  ```bash
  sudo usermod -a -G dialout $USER
  ```
  Then log out and back in.

### Configuration Issues
- Ensure the config file exists and is valid
- Check that the radar is in the correct mode
- Verify baud rates match the radar configuration

### Performance Issues
- Reduce `history_length` for better performance
- Increase animation `interval` in `start_visualization()` method
- Close other applications using significant CPU/memory

### No Data Display
- Check COM port connections
- Verify radar configuration
- Ensure the radar is actively transmitting data
- Check for error messages in the terminal

## Data Structure

The visualizer processes the following data from the radar:

- **Point Cloud**: X, Y, Z coordinates, Doppler, SNR, Noise, Track index
- **Height Data**: Track ID, max height, min height
- **Track Data**: Track ID, position (X,Y,Z), velocity, acceleration, confidence

## Integration with Fall Detection

The visualizer is compatible with the fall detection system. Height data and track information are displayed in real-time, making it easy to monitor for fall events.

## Technical Notes

- Uses threading for data acquisition to prevent blocking the GUI
- Implements a queue-based system for thread-safe data transfer
- Automatically handles frame synchronization and data parsing
- Supports both Windows and Linux platforms
- Compatible with xWR6843 radar family 