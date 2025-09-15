import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import matplotlib.animation as animation
from datastream import UARTParser
import time
from serial.tools import list_ports
import platform
import threading
import queue
from collections import deque
import sys

class RealtimeRadarVisualizer:
    def __init__(self, max_points=1000, history_length=50):
        """
        Initialize the real-time radar visualizer
        
        Args:
            max_points: Maximum number of points to display in point cloud
            history_length: Number of frames to keep in history for persistent display
        """
        self.max_points = max_points
        self.history_length = history_length
        
        # Data storage
        self.point_cloud_history = deque(maxlen=history_length)
        self.height_data_history = deque(maxlen=history_length)
        self.track_data_history = deque(maxlen=history_length)
        
        # Threading for data acquisition
        self.data_queue = queue.Queue()
        self.running = False
        
        # UART Parser setup
        self.parser = UARTParser(type="DoubleCOMPort")
        
        # Setup the figure with subplots
        self.setup_plots()
        
        # Animation object
        self.ani = None
        
    def setup_plots(self):
        """Setup matplotlib figure and subplots"""
        self.fig = plt.figure(figsize=(16, 10))
        
        # 3D Point Cloud Plot (main plot)
        self.ax_3d = self.fig.add_subplot(221, projection='3d')
        self.ax_3d.set_title('3D Point Cloud (Real-time)', fontsize=14, fontweight='bold')
        self.ax_3d.set_xlabel('X (m)')
        self.ax_3d.set_ylabel('Y (m)')
        self.ax_3d.set_zlabel('Z (m)')
        
        # Set initial limits
        self.ax_3d.set_xlim([-3, 3])
        self.ax_3d.set_ylim([0, 6])
        self.ax_3d.set_zlim([0, 3])
        
        # Height Data Plot
        self.ax_height = self.fig.add_subplot(222)
        self.ax_height.set_title('Track Heights', fontsize=14, fontweight='bold')
        self.ax_height.set_xlabel('Track ID')
        self.ax_height.set_ylabel('Height (m)')
        self.ax_height.set_ylim([0, 3])
        
        # Top-down view (X-Y plane)
        self.ax_top = self.fig.add_subplot(223)
        self.ax_top.set_title('Top-down View (X-Y)', fontsize=14, fontweight='bold')
        self.ax_top.set_xlabel('X (m)')
        self.ax_top.set_ylabel('Y (m)')
        self.ax_top.set_xlim([-3, 3])
        self.ax_top.set_ylim([0, 6])
        self.ax_top.grid(True, alpha=0.3)
        
        # Statistics and Info Panel
        self.ax_info = self.fig.add_subplot(224)
        self.ax_info.set_title('System Information', fontsize=14, fontweight='bold')
        self.ax_info.axis('off')
        
        plt.tight_layout()
        
    def connect_radar(self, cli_com=None, data_com=None):
        """
        Connect to radar COM ports
        
        Args:
            cli_com: CLI COM port (auto-detected if None)
            data_com: Data COM port (auto-detected if None)
        """
        if cli_com is None or data_com is None:
            cli_com, data_com = self.auto_detect_ports()
            
        try:
            self.parser.connectComPorts(cli_com, data_com)
            print(f"Connected to CLI: {cli_com}, Data: {data_com}")
            return True
        except Exception as e:
            print(f"Failed to connect to COM ports: {e}")
            return False
            
    def auto_detect_ports(self):
        """Auto-detect radar COM ports based on system"""
        CLI_SIL_SERIAL_PORT_NAME = 'Enhanced COM Port'
        DATA_SIL_SERIAL_PORT_NAME = 'Standard COM Port'
        
        system = platform.system()
        cli_com = None
        data_com = None
        
        if system == "Linux":
            cli_com = '/dev/ttyUSB0'
            data_com = '/dev/ttyUSB1'
        elif system == "Windows":
            serial_ports = list(list_ports.comports())
            for port in serial_ports:
                if CLI_SIL_SERIAL_PORT_NAME in port.description:   
                    cli_com = port.device
                if DATA_SIL_SERIAL_PORT_NAME in port.description:
                    data_com = port.device
                    
            if cli_com is None or data_com is None:
                print("COM ports not auto-detected. Available ports:")
                for port in serial_ports:
                    print(f"  {port.device}: {port.description}")
                cli_com = input("Enter CLI COM port: ")
                data_com = input("Enter DATA COM port: ")
                
        return cli_com, data_com
        
    def configure_radar(self, config_file="Final_config_6m.cfg"):
        """Configure the radar with the specified config file"""
        try:
            # Check if device is already configured
            last_byte = self.parser.dataCom.read(1)
            if len(last_byte) < 1:
                print("Device not configured, applying configuration...")
                self.parse_and_send_config(config_file)
            else:
                print("Device already configured")
        except Exception as e:
            print(f"Configuration error: {e}")
            
    def parse_and_send_config(self, config_file):
        """Parse and send configuration to radar"""
        try:
            with open(config_file, "r") as cfg_file:
                cfg = cfg_file.readlines()
                self.parser.cfg = cfg
                self.parser.demo = "3D People Tracking"
                self.parser.device = "xWR6843"
                self.parser.sendCfg(cfg)
                print(f"Configuration sent from {config_file}")
        except Exception as e:
            print(f"Failed to send configuration: {e}")
            
    def data_acquisition_thread(self):
        """Thread function for continuous data acquisition"""
        while self.running:
            try:
                # Read and parse UART data
                frame_data = self.parser.readAndParseUartDoubleCOMPort()
                
                # Put data in queue for main thread
                self.data_queue.put(frame_data)
                
            except Exception as e:
                print(f"Data acquisition error: {e}")
                time.sleep(0.1)
                
    def update_visualization(self, frame):
        """Update function called by matplotlib animation"""
        # Process all available data from queue
        latest_data = None
        while not self.data_queue.empty():
            try:
                latest_data = self.data_queue.get_nowait()
            except queue.Empty:
                break
                
        if latest_data is None:
            return
            
        # Store data in history
        self.point_cloud_history.append(latest_data.get('pointCloud', np.array([])))
        self.height_data_history.append(latest_data.get('heightData', np.array([])))
        self.track_data_history.append(latest_data.get('trackData', np.array([])))
        
        # Clear all plots
        self.ax_3d.clear()
        self.ax_height.clear()
        self.ax_top.clear()
        self.ax_info.clear()
        
        # Update 3D point cloud
        self.update_3d_plot(latest_data)
        
        # Update height plot
        self.update_height_plot(latest_data)
        
        # Update top-down view
        self.update_top_view(latest_data)
        
        # Update info panel
        self.update_info_panel(latest_data)
        
    def update_3d_plot(self, data):
        """Update 3D point cloud plot"""
        self.ax_3d.set_title('3D Point Cloud (Real-time)', fontsize=14, fontweight='bold')
        self.ax_3d.set_xlabel('X (m)')
        self.ax_3d.set_ylabel('Y (m)')
        self.ax_3d.set_zlabel('Z (m)')
        
        # Combine recent point clouds for persistent display
        combined_points = []
        alpha_values = []
        
        for i, points in enumerate(self.point_cloud_history):
            if len(points) > 0:
                combined_points.append(points)
                # Fade older points
                alpha = 0.3 + 0.7 * (i / len(self.point_cloud_history))
                alpha_values.extend([alpha] * len(points))
                
        if combined_points:
            all_points = np.vstack(combined_points)
            
            # Color points by height (Z coordinate)
            colors = plt.cm.viridis(all_points[:, 2] / 3.0)  # Normalize by max height
            
            self.ax_3d.scatter(all_points[:, 0], all_points[:, 1], all_points[:, 2], 
                             c=colors, s=20, alpha=0.7)
                             
        # Plot tracks if available
        if 'trackData' in data and len(data['trackData']) > 0:
            tracks = data['trackData']
            for track in tracks:
                tid = int(track[0])
                x, y, z = track[1], track[2], track[3]
                
                # Plot track position as larger marker
                self.ax_3d.scatter([x], [y], [z], c='red', s=100, marker='o', 
                                 edgecolors='black', linewidth=2)
                
                # Add track ID label
                self.ax_3d.text(x, y, z + 0.1, f'T{tid}', fontsize=10, fontweight='bold')
        
        self.ax_3d.set_xlim([-3, 3])
        self.ax_3d.set_ylim([0, 6])
        self.ax_3d.set_zlim([0, 3])
        
    def update_height_plot(self, data):
        """Update height data plot"""
        self.ax_height.set_title('Track Heights', fontsize=14, fontweight='bold')
        self.ax_height.set_xlabel('Track ID')
        self.ax_height.set_ylabel('Height (m)')
        
        if 'heightData' in data and len(data['heightData']) > 0:
            heights = data['heightData']
            track_ids = heights[:, 0]
            max_heights = heights[:, 1]
            min_heights = heights[:, 2]
            
            # Create bar chart
            bars = self.ax_height.bar(track_ids, max_heights, alpha=0.7, color='skyblue', 
                                    edgecolor='navy', linewidth=1)
            
            # Add height values on bars
            for i, (tid, height) in enumerate(zip(track_ids, max_heights)):
                self.ax_height.text(tid, height + 0.05, f'{height:.2f}m', 
                                  ha='center', va='bottom', fontweight='bold')
                                  
            self.ax_height.set_ylim([0, max(3, np.max(max_heights) * 1.2)])
        else:
            self.ax_height.text(0.5, 0.5, 'No height data', ha='center', va='center', 
                              transform=self.ax_height.transAxes, fontsize=12)
            
        self.ax_height.grid(True, alpha=0.3)
        
    def update_top_view(self, data):
        """Update top-down view (X-Y plane)"""
        self.ax_top.set_title('Top-down View (X-Y)', fontsize=14, fontweight='bold')
        self.ax_top.set_xlabel('X (m)')
        self.ax_top.set_ylabel('Y (m)')
        
        # Plot recent point clouds
        for i, points in enumerate(list(self.point_cloud_history)[-5:]):  # Last 5 frames
            if len(points) > 0:
                alpha = 0.2 + 0.6 * (i / 5)
                self.ax_top.scatter(points[:, 0], points[:, 1], 
                                  c=points[:, 2], cmap='viridis', s=10, alpha=alpha)
                                  
        # Plot tracks
        if 'trackData' in data and len(data['trackData']) > 0:
            tracks = data['trackData']
            for track in tracks:
                tid = int(track[0])
                x, y = track[1], track[2]
                
                self.ax_top.scatter([x], [y], c='red', s=100, marker='o', 
                                  edgecolors='black', linewidth=2)
                self.ax_top.text(x + 0.1, y + 0.1, f'T{tid}', fontsize=10, fontweight='bold')
                
        self.ax_top.set_xlim([-3, 3])
        self.ax_top.set_ylim([0, 6])
        self.ax_top.grid(True, alpha=0.3)
        
    def update_info_panel(self, data):
        """Update information panel"""
        self.ax_info.set_title('System Information', fontsize=14, fontweight='bold')
        self.ax_info.axis('off')
        
        info_text = []
        
        # Frame information
        if 'frameNum' in data:
            info_text.append(f"Frame: {data['frameNum']}")
            
        # Point cloud info
        if 'numDetectedPoints' in data:
            info_text.append(f"Points: {data['numDetectedPoints']}")
        elif 'pointCloud' in data:
            info_text.append(f"Points: {len(data['pointCloud'])}")
            
        # Track info
        if 'numDetectedTracks' in data:
            info_text.append(f"Tracks: {data['numDetectedTracks']}")
        elif 'trackData' in data:
            info_text.append(f"Tracks: {len(data['trackData'])}")
            
        # Height info
        if 'numDetectedHeights' in data:
            info_text.append(f"Heights: {data['numDetectedHeights']}")
        elif 'heightData' in data:
            info_text.append(f"Heights: {len(data['heightData'])}")
            
        # Current time
        info_text.append(f"Time: {time.strftime('%H:%M:%S')}")
        
        # Display fall detection alerts
        if 'heightData' in data and 'trackData' in data:
            heights = data.get('heightData', [])
            tracks = data.get('trackData', [])
            
            for height in heights:
                for track in tracks:
                    if int(track[0]) == int(height[0]):
                        tid = int(height[0])
                        height_val = height[1]
                        info_text.append(f"Track {tid}: {height_val:.2f}m")
                        
        # Join and display text
        full_text = '\n'.join(info_text)
        self.ax_info.text(0.05, 0.95, full_text, transform=self.ax_info.transAxes, 
                         fontsize=12, verticalalignment='top', fontfamily='monospace')
        
    def start_visualization(self):
        """Start the real-time visualization"""
        self.running = True
        
        # Start data acquisition thread
        self.data_thread = threading.Thread(target=self.data_acquisition_thread)
        self.data_thread.daemon = True
        self.data_thread.start()
        
        # Start animation
        self.ani = animation.FuncAnimation(self.fig, self.update_visualization, 
                                         interval=100, blit=False, cache_frame_data=False)
        
        plt.show()
        
    def stop_visualization(self):
        """Stop the visualization"""
        self.running = False
        if self.ani:
            self.ani.event_source.stop()


def main():
    """Main function to run the visualizer"""
    print("=== Real-time Radar Visualizer ===")
    print("Initializing visualizer...")
    
    # Create visualizer
    visualizer = RealtimeRadarVisualizer(max_points=1000, history_length=30)
    
    # Connect to radar
    print("Connecting to radar...")
    if not visualizer.connect_radar():
        print("Failed to connect to radar. Exiting.")
        return
        
    # Configure radar
    print("Configuring radar...")
    visualizer.configure_radar()
    
    print("Starting visualization...")
    print("Press Ctrl+C to stop")
    
    try:
        visualizer.start_visualization()
    except KeyboardInterrupt:
        print("\nStopping visualization...")
        visualizer.stop_visualization()
    except Exception as e:
        print(f"Error during visualization: {e}")
    finally:
        print("Visualization stopped.")


if __name__ == "__main__":
    main() 