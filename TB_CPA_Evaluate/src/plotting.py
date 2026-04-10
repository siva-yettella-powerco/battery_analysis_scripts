import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt


def plot_cell_data(cell_df, ocv_table=None, pulses_steps=None, skip_points=20, title='Cell Data Visualization'):
    # Create subplots with 2 rows and 1 column, sharing x-axis
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, subplot_titles=("Temperature profile", "Voltage profile","Current profile"), vertical_spacing=0.05)

    # Prepare x-axis data
    x_data = cell_df['Unix_datetime'][::skip_points]

    # Plot temperature data on the first subplot
    fig.add_trace(go.Scatter(x=x_data, y=cell_df['T_Chamber_degC'][::skip_points], name='T_Chamber_degC'), row=1, col=1)
    fig.add_trace(go.Scatter(x=x_data, y=cell_df['T_Cell_degC'][::skip_points], name='T_Cell_degC'), row=1, col=1)
    fig.add_trace(go.Scatter(x=x_data, y=cell_df['T_Cathode_degC'][::skip_points], name='T_Cathode_degC'), row=1, col=1)
    fig.add_trace(go.Scatter(x=x_data, y=cell_df['T_Anode_degC'][::skip_points], name='T_Anode_degC'), row=1, col=1)

    custom_voltage = np.stack([
        cell_df['SOC_corrected'][::skip_points],
        cell_df['Current_A'][::skip_points]
    ], axis=-1)

    # Plot voltage data on the second subplot
    fig.add_trace(go.Scatter(x=x_data, y=cell_df['Voltage_V'][::skip_points], name='Voltage_V', legendgroup='Voltage_V',
            customdata=custom_voltage,
            hovertemplate=(
                'Time: %{x}<br>'
                'Voltage: %{y}<br>'
                'SOC: %{customdata[0]}<br>'
                'Current: %{customdata[1]}'
                '<extra></extra>')), row=2, col=1)

    custom_current = np.stack([
        cell_df['Step_id'][::skip_points],
        cell_df['Capacity_step_Ah'][::skip_points],
        cell_df['Q_std'][::skip_points]
    ], axis=-1)

    # Plot current data on the third subplot
    fig.add_trace(go.Scatter(x=x_data, y=cell_df['Current_A'][::skip_points], name='Current_A', legendgroup='Current_A',
                             customdata=custom_current,
                             hovertemplate='Time: %{x}<br>'
                                           'Current: %{y}<br>'
                                           'StepID: %{customdata[0]}<br>'
                                           'Capacity_step_Ah: %{customdata[1]}<br>'
                                           'Q_std: %{customdata[2]}<extra></extra>'
                             ), row=3, col=1)

    # Add filtered voltage data from ocv_table
    if ocv_table is not None:
        fig.add_trace(go.Scatter(x=ocv_table['Unix_datetime'], y=ocv_table['Voltage_filt_V'], name='OCV extracted', mode='markers'), row=2, col=1)

    if pulses_steps:
        for pulse_step in pulses_steps:
            tempdata = cell_df[::skip_points]
            tempdata = tempdata[tempdata['Step_id'] == pulse_step]
            fig.add_trace(go.Scatter(x=tempdata['Unix_datetime'], y=tempdata['Voltage_V'], name='Voltage_V', legendgroup='Voltage_V', showlegend=False, marker={'color':'black'}), row=2, col=1)
            fig.add_trace(go.Scatter(x=tempdata['Unix_datetime'], y=tempdata['Current_A'], name='Current_A', legendgroup='Current_A', showlegend=False, marker={'color':'black'}), row=3, col=1)

    # Update layout
    fig.update_layout(title_text=title, template='plotly_white', height=600)
    fig.update_xaxes(title_text='Datetime', row=3, col=1, showticklabels=True)
    fig.update_yaxes(title_text='Temperatures (degC)', row=1, col=1)
    fig.update_yaxes(title_text='Voltage (V)', row=2, col=1)
    fig.update_yaxes(title_text='Current (A)', row=3, col=1)

    fig.update_layout(height=1080, width=1400, hovermode='x unified')
    fig.update_layout(hoversubplots="axis")
    return fig


def plot_ocv_vs_soc(ocv_table, cell_id):
    """OCV vs SOC colored by temperature, with repeat measurements as dotted/open-circle."""
    df_repeat_0 = ocv_table[ocv_table['Repeat'] == 0]
    df_repeat_gt_0 = ocv_table[ocv_table['Repeat'] > 0]

    fig = px.line(
        df_repeat_0,
        x='SOC_corrected',
        y='Voltage_filt_V',
        color='T_set',
        markers=True,
        title=f'OCV vs SOC : {cell_id}',
        labels={
            'SOC_corrected': 'SOC_actual (%)',
            'Voltage_filt_V': 'OCV (V)',
            'T_set': 'Temperature_set (degC)'
        }
    )

    for t_value in df_repeat_gt_0['T_set'].unique():
        df_subset = df_repeat_gt_0[df_repeat_gt_0['T_set'] == t_value]
        fig.add_trace(go.Scatter(
            x=df_subset['SOC_corrected'],
            y=df_subset['Voltage_filt_V'],
            mode='lines+markers',
            name=f'{t_value} (Repeat)',
            marker=dict(symbol='circle-open'),
            line=dict(dash='dot')
        ))

    fig.update_layout(template='plotly_white')
    return fig


def plot_dual_axis(df, x_col, y1_cols=[], y2_cols=[], skip_points=20, title=''):
    """Dual Y-axis plot with primary and secondary traces."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    x_data = df[x_col][::skip_points]

    for y_col in y1_cols:
        y_data = df[y_col][::skip_points]
        fig.add_trace(go.Scatter(x=x_data, y=y_data, name=y_col), secondary_y=False)

    for y_col in y2_cols:
        y_data = df[y_col][::skip_points]
        fig.add_trace(go.Scatter(x=x_data, y=y_data, name=y_col), secondary_y=True)

    fig.update_xaxes(title_text=x_col)
    fig.update_layout(title_text=title)
    fig.update_yaxes(title_text=" / ".join(filter(None, y1_cols)), secondary_y=False)
    fig.update_yaxes(title_text=" / ".join(filter(None, y2_cols)), secondary_y=True)

    return fig


def plot_QC_subplots(temp_df, title_text='', fig=None):
    """QC analysis 2-panel: Voltage/Current + Temperature/SOC with SOC reference lines."""
    if fig is None:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.1,
            specs=[[{"secondary_y": True}], [{"secondary_y": True}]]
        )

    time_ser = (temp_df['Unix_total_time'] - temp_df['Unix_total_time'].iloc[0]) / 60
    temp_df['Step_time_min'] = time_ser

    # Row 1: Voltage and Current
    fig.add_trace(
        go.Scatter(x=temp_df['Step_time_min'], y=temp_df['Voltage_V'],
                   name='Voltage (V)', line=dict(color='blue')),
        row=1, col=1, secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=temp_df['Step_time_min'], y=temp_df['Current_A'],
                   name='Current (A)', line=dict(color='red', dash='dash')),
        row=1, col=1, secondary_y=True
    )

    # Row 2: Temperature and SOC
    fig.add_trace(
        go.Scatter(x=temp_df['Step_time_min'], y=temp_df['T_Cell_degC'],
                   name='Cell Temp (degC)', line=dict(color='green')),
        row=2, col=1, secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=temp_df['Step_time_min'], y=temp_df['T_Chamber_degC'],
                   name='Chamber Temp (degC)', line=dict(color='darkturquoise')),
        row=2, col=1, secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=temp_df['Step_time_min'], y=temp_df['T_cold_degC'],
                   name='Cold-spot Temp (degC)', line=dict(color='cornflowerblue')),
        row=2, col=1, secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=temp_df['Step_time_min'], y=temp_df['SOC_corrected'],
                   name='SOC (%)', line=dict(color='orange', dash='dash')),
        row=2, col=1, secondary_y=True
    )

    # SOC reference lines
    soc_8_index = (temp_df['SOC_corrected'] - 8).abs().idxmin()
    soc_80_index = (temp_df['SOC_corrected'] - 80).abs().idxmin()
    date_8 = temp_df.loc[soc_8_index, 'Step_time_min']
    date_80 = temp_df.loc[soc_80_index, 'Step_time_min']

    min_temp = int(temp_df['T_Chamber_degC'].min()) - 1
    max_temp = max(min_temp + 15, int(temp_df['T_Cell_degC'].max())) + 1

    fig.update_layout(
        title=title_text,
        template='plotly_white',
        height=800,
        legend=dict(x=1.05),
        margin=dict(t=50, b=50),
        shapes=[
            dict(type='line', xref='x', yref='paper', x0=date_8, x1=date_8,
                 y0=0, y1=1, line=dict(color='purple', width=2, dash='dot')),
            dict(type='line', xref='x', yref='paper', x0=date_80, x1=date_80,
                 y0=0, y1=1, line=dict(color='purple', width=2, dash='dot'))
        ],
        annotations=[
            dict(x=date_8, y=-0.05, xref='x', yref='paper', text='SOC=8%',
                 showarrow=False, font=dict(color='purple')),
            dict(x=date_80, y=-0.05, xref='x', yref='paper', text='SOC=80%',
                 showarrow=False, font=dict(color='purple'))
        ]
    )

    fig.update_xaxes(title_text='Time (min)', showline=True, linewidth=1, linecolor='black', mirror=True, showticklabels=True, row=2, col=1)
    fig.update_xaxes(title_text='Time (min)', showline=True, linewidth=1, linecolor='black', mirror=True, showticklabels=True, row=1, col=1)
    fig.update_yaxes(title_text='Voltage (V)', showline=True, linewidth=1, linecolor='black', mirror=True, row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text='Current (A)', row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text='Temperature (degC)', range=[min_temp, max_temp], showline=True, linewidth=1, linecolor='black', mirror=True, row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text='SOC (%)', row=2, col=1, secondary_y=True)

    return fig


def general_dual_axis_plot(
    df,
    y1_col=None,
    x_col=None,
    y1_name=None,
    title='',
    x_title='x-axis',
    y1_title='y-axis',
    fig=None,

    # --- secondary-axis options ---
    y2_col=None,
    y2_name=None,
    y2_title='secondary y-axis',

    # --- styling ---
    y1_mode='lines',
    y2_mode='lines',
    y1_line_color=None,
    y2_line_color=None,
    y1_line_dash='solid',
    y2_line_dash='solid',
    y1_marker_symbol=None,
    y2_marker_symbol=None,

    y1_size=1.0,
    y2_size=1.0,

    show_legend=True,
    separate_y2_legend=True,
):
    """
    Dual Y-axis plot with unified line+marker scaling.

    y1_mode / y2_mode       : "lines", "markers", or "lines+markers"
    y1_line_dash / y2_line_dash : "solid", "dot", "dash", "longdash", "dashdot", "longdashdot"
    y1_marker_symbol        : Plotly marker symbol string (e.g. "circle", "square", "diamond")
    show_legend             : True / False
    """
    if fig is None:
        fig = make_subplots(rows=1, cols=1, specs=[[{"secondary_y": True}]])

    if (x_col is None) or x_col == 'index':
        x_data = df.index
    else:
        x_data = df[x_col]

    # Primary trace
    if y1_col is not None:
        y1_data = df[y1_col]
        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=y1_data,
                name=(y1_name or y1_col),
                mode=y1_mode,
                line=dict(
                    color=y1_line_color,
                    dash=y1_line_dash,
                    width=2 * y1_size
                ) if (y1_line_color or y1_line_dash) else dict(width=2 * y1_size),
                showlegend=show_legend,
                legendgroup=y1_name,
                marker=dict(
                    symbol=y1_marker_symbol,
                    size=6 * y1_size
                ) if ("markers" in y1_mode) else None,
            ),
            secondary_y=False, row=1, col=1,
        )

    # Secondary trace (optional)
    if y2_col is not None:
        y2_data = df[y2_col]
        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=y2_data,
                name=(y2_name or y2_col),
                mode=y2_mode,
                line=dict(
                    color=y2_line_color,
                    dash=y2_line_dash,
                    width=2 * y2_size
                ) if (y2_line_color or y2_line_dash) else dict(width=2 * y2_size),
                showlegend=True if separate_y2_legend else False,
                legendgroup=y2_name if separate_y2_legend else y1_name,
                marker=dict(
                    symbol=y2_marker_symbol,
                    size=6 * y2_size
                ) if ("markers" in y2_mode) else None,
            ),
            secondary_y=True, row=1, col=1,
        )

    fig.update_layout(
        title_text=title,
        template="plotly_white",
        hovermode='x unified',
    )

    fig.update_xaxes(title_text=x_title, showline=True, linewidth=1, linecolor='black', mirror=True)
    if y1_col is not None:
        fig.update_yaxes(title_text=y1_title, secondary_y=False, showline=True, linewidth=1, linecolor='black', mirror=True)
    if y2_col is not None:
        fig.update_yaxes(title_text=y2_title, secondary_y=True, showline=True, linewidth=1, linecolor='black', mirror=True)

    return fig


def get_color_for_range(value, min_value, max_value, cmap='viridis'):
    '''
    # cmap = 'viridis', 'plasma', 'Blues', 'Greens','RdPu', 'BuPu', 'OrRd', 'winter', 'cool'
    :return: a color for a range of value, hence color is value dependent
    '''
    normalized_value = (value - min_value) / (max_value - min_value)
    colormap = plt.cm.get_cmap(cmap)
    color = colormap(normalized_value)
    hex_color = mcolors.to_hex(color)
    return hex_color


def plot_surface_from_table(
    interpolated_df,
    original_df=None,
    *,
    plot_interpolated_points: bool = False,
    x_axis: dict = None,
    y_axis: dict = None,
    z_axis: dict = None,
    surface_opacity=0.9,
    grid_color="black",
    title=None,
    colorscale="Viridis",
):
    '''
    ## INPUT PARAMETERS:
    - interpolated_df: dataframe which is considered for surface plot
    - original_df: dataframe which is considered for plotting only markers
    - x,y,z_axis = {
                "label": "Temperature [°C]",
                "dtick": 5,
                "range": [-20, 60],
                "ticksuffix": " °C",
                "tickformat": None,
                "mesh": True,
                }
    - colorscale = Plasma, Viridis, Cividis, Inferno, Magma, YlOrRd, YlGnBu
    - surface_opacity = 0 for only mesh plot
    '''
    x_axis = x_axis or {}
    y_axis = y_axis or {}
    z_axis = z_axis or {}

    x_vals = interpolated_df.columns.astype(float).values
    y_vals = interpolated_df.index.astype(float).values
    Z = interpolated_df.values.astype(float)

    X_mesh, Y_mesh = np.meshgrid(x_vals, y_vals)

    fig = go.Figure()

    contours = {
        "x": dict(show=True, color=grid_color) if x_axis.get("mesh") else None,
        "y": dict(show=True, color=grid_color) if y_axis.get("mesh") else None,
        "z": dict(show=True, color=grid_color) if z_axis.get("mesh") else None,
    }
    contours = {k: v for k, v in contours.items() if v is not None} or None

    fig.add_trace(
        go.Surface(
            x=X_mesh,
            y=Y_mesh,
            z=Z,
            colorscale=colorscale,
            opacity=surface_opacity,
            contours=contours,
            name="Interpolated surface",
            hovertemplate=(
                f"{y_axis.get('label')}: %{{y}} °C<br>"
                f"{x_axis.get('label')}: %{{x}} %<br>"
                f"{z_axis.get('label')}: %{{z:.2f}} mΩ<br>"
                "<extra>Interpolated surface</extra>"
            ),
            colorbar=dict(title=z_axis.get("label", "Z")),
        )
    )

    if original_df is not None and not original_df.empty:
        orig = original_df.astype(float)
        mask = ~np.isnan(orig.values)
        if mask.any():
            iy, ix = np.where(mask)
            x_pts = orig.columns.values[ix]
            y_pts = orig.index.values[iy]
            z_pts = orig.values[mask]

            fig.add_trace(
                go.Scatter3d(
                    x=x_pts, y=y_pts, z=z_pts,
                    mode="markers",
                    marker=dict(size=3, color="red", opacity=1.0),
                    name="Original data",
                    showlegend=False,
                    hovertemplate=(
                        f"{y_axis.get('label')}: %{{y}} °C<br>"
                        f"{x_axis.get('label')}: %{{x}} %<br>"
                        f"{z_axis.get('label')}: %{{z:.2f}} mΩ<br>"
                        "<extra>Original data</extra>"
                    )
                )
            )

    if plot_interpolated_points and not interpolated_df.empty:
        interp = interpolated_df.astype(float)
        interp_mask = ~np.isnan(interp.values)

        if original_df is not None and not original_df.empty:
            original_aligned = original_df.reindex(index=interp.index, columns=interp.columns)
            orig_mask = ~np.isnan(original_aligned.values)
            interp_mask &= ~orig_mask

        if interp_mask.any():
            iy, ix = np.where(interp_mask)
            x_ip = interp.columns.values[ix]
            y_ip = interp.index.values[iy]
            z_ip = interp.values[interp_mask]

            fig.add_trace(
                go.Scatter3d(
                    x=x_ip, y=y_ip, z=z_ip,
                    mode="markers",
                    marker=dict(size=5, color="blue", opacity=0.7, symbol="circle-open"),
                    name="Interpolated points",
                    showlegend=False,
                    hovertemplate=(
                        f"{y_axis.get('label')}: %{{y}} °C<br>"
                        f"{x_axis.get('label')}: %{{x}} %<br>"
                        f"{z_axis.get('label')}: %{{z:.2f}} mΩ<br>"
                        "<extra>Interpolated</extra>"
                    ),
                )
            )

    fig.update_layout(
        template="plotly_white",
        title=title,
        scene=dict(
            xaxis=dict(
                title=x_axis.get("label"),
                dtick=x_axis.get("dtick"),
                range=x_axis.get("range"),
                tickformat=x_axis.get("tickformat"),
                ticksuffix=x_axis.get("ticksuffix"),
            ),
            yaxis=dict(
                title=y_axis.get("label"),
                dtick=y_axis.get("dtick"),
                range=y_axis.get("range"),
                tickformat=y_axis.get("tickformat"),
                ticksuffix=y_axis.get("ticksuffix"),
            ),
            zaxis=dict(
                title=z_axis.get("label"),
                dtick=z_axis.get("dtick"),
                range=z_axis.get("range"),
                tickformat=z_axis.get("tickformat"),
                ticksuffix=z_axis.get("ticksuffix"),
            ),
        ),
        margin=dict(l=0, r=0, b=0, t=40),
    )

    return fig
