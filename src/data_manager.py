"""
Data Manager Module
Handles all data loading, processing, and management operations
"""

import pandas as pd
import streamlit as st
import re
from typing import Tuple, Optional, Dict, List

@st.cache_data
def load_data() -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Load data from Cutlass time entry Excel file with caching
    
    Returns:
        Tuple of (cutlass_df, completion_notes_df, None) or (None, None, None) if error
    """
    try:
        cutlass_df = pd.read_excel("Cutlass_time_entry.xlsx")
        
        # Filter to only include WO Type = Corrective, Project, Ad Hoc
        cutlass_df = cutlass_df[cutlass_df['WO Type'].isin(['Corrective', 'Project', 'Ad Hoc'])].copy()
        
        # Create a separate dataframe for completion notes suggestions
        completion_notes_df = cutlass_df[['Completion Notes', 'WO Type', 'Time Type']].dropna()
        completion_notes_df = completion_notes_df.drop_duplicates(subset=['Completion Notes'])
        
        return cutlass_df, completion_notes_df, None
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None, None, None

def get_technician_options(cutlass_df: pd.DataFrame) -> Tuple[List[str], Dict[str, str]]:
    """
    Generate technician dropdown options and mapping from Cutlass data
    
    Args:
        cutlass_df: Cutlass time entry dataframe
        
    Returns:
        Tuple of (tech_options_list, tech_mapping_dict)
    """
    # Extract unique technicians from the 'User Resource: Full Name' column
    tech_names = cutlass_df[["User Resource: Full Name"]].dropna().drop_duplicates()
    
    tech_options = ["-- Select Technician --"]
    tech_mapping = {}
    
    for _, row in tech_names.iterrows():
        full_name = row['User Resource: Full Name']
        display_name = full_name
        tech_options.append(display_name)
        tech_mapping[display_name] = full_name
    
    return tech_options, tech_mapping

def get_month_year_options(cutlass_df: pd.DataFrame) -> Tuple[List[str], Dict[str, str]]:
    """
    Generate month-year dropdown options from Cutlass data
    
    Args:
        cutlass_df: Cutlass time entry dataframe
        
    Returns:
        Tuple of (month_year_options_list, month_year_mapping_dict)
    """
    # Try to use Year and Month columns first, fall back to Month Year
    if 'Year' in cutlass_df.columns and 'Month' in cutlass_df.columns:
        # Create month-year combinations from Year and Month columns
        year_month_df = cutlass_df[['Year', 'Month']].dropna().drop_duplicates()
        
        # Create month-year strings and sort them properly
        month_years = []
        for _, row in year_month_df.iterrows():
            year = int(row['Year'])
            month = int(row['Month'])
            # Create datetime to get proper month name, then format
            import datetime
            month_name = datetime.date(year, month, 1).strftime('%b %Y')
            month_years.append(month_name)
        
        # Sort by actual date (ascending order - oldest first)
        month_years = sorted(set(month_years), key=lambda x: datetime.datetime.strptime(x, '%b %Y'))
    else:
        # Fall back to Month Year column
        month_years = cutlass_df['Month Year'].dropna().unique()
        # Convert to proper datetime for sorting, then back to string
        import datetime
        try:
            month_years = sorted(set(month_years), key=lambda x: datetime.datetime.strptime(x, '%b %Y'))
        except:
            # If parsing fails, just sort alphabetically
            month_years = sorted(set(month_years))
    
    month_year_options = ["-- All Months --"] + list(month_years)
    month_year_mapping = {"-- All Months --": None}
    
    for my in month_years:
        month_year_mapping[my] = my
    
    return month_year_options, month_year_mapping

def get_technician_month_year_options(cutlass_df: pd.DataFrame, selected_tech: str) -> Tuple[List[str], Dict[str, str]]:
    """
    Generate month-year dropdown options for a specific technician from Cutlass data
    
    Args:
        cutlass_df: Cutlass time entry dataframe
        selected_tech: Selected technician name
        
    Returns:
        Tuple of (month_year_options_list, month_year_mapping_dict)
    """
    # Filter data for the selected technician
    tech_data = cutlass_df[cutlass_df["User Resource: Full Name"] == selected_tech]
    
    if len(tech_data) == 0:
        return ["-- No data available --"], {"-- No data available --": None}
    
    # Try to use Year and Month columns first, fall back to Month Year
    if 'Year' in tech_data.columns and 'Month' in tech_data.columns:
        # Create month-year combinations from Year and Month columns
        year_month_df = tech_data[['Year', 'Month']].dropna().drop_duplicates()
        
        # Create month-year strings and sort them properly
        month_years = []
        for _, row in year_month_df.iterrows():
            year = int(row['Year'])
            month = int(row['Month'])
            # Create datetime to get proper month name, then format
            import datetime
            month_name = datetime.date(year, month, 1).strftime('%b %Y')
            month_years.append(month_name)
        
        # Sort by actual date (ascending order - oldest first)
        month_years = sorted(set(month_years), key=lambda x: datetime.datetime.strptime(x, '%b %Y'))
    else:
        # Fall back to Month Year column
        month_years = tech_data['Month Year'].dropna().unique()
        # Convert to proper datetime for sorting, then back to string
        import datetime
        try:
            month_years = sorted(set(month_years), key=lambda x: datetime.datetime.strptime(x, '%b %Y'))
        except:
            # If parsing fails, just sort alphabetically
            month_years = sorted(set(month_years))
    
    month_year_options = ["-- All Months --"] + list(month_years)
    month_year_mapping = {"-- All Months --": None}
    
    for my in month_years:
        month_year_mapping[my] = my
    
    return month_year_options, month_year_mapping

def get_work_order_options(selected_tech: str, cutlass_df: pd.DataFrame, selected_month_year: str = None) -> Tuple[List[str], Dict[str, str]]:
    """
    Generate work order dropdown options for selected technician from Cutlass data
    
    Args:
        selected_tech: Selected technician name
        cutlass_df: Cutlass time entry dataframe
        selected_month_year: Selected month year filter (optional)
        
    Returns:
        Tuple of (wo_options_list, wo_mapping_dict)
    """
    # Filter work orders for the selected technician
    tech_work_orders = cutlass_df[cutlass_df["User Resource: Full Name"] == selected_tech]
    
    # Apply month/year filter if provided
    if selected_month_year:
        # Try to filter using Month Year column first
        if "Month Year" in tech_work_orders.columns:
            tech_work_orders = tech_work_orders[tech_work_orders["Month Year"] == selected_month_year]
        elif 'Year' in tech_work_orders.columns and 'Month' in tech_work_orders.columns:
            # Create month-year string from Year and Month columns for comparison
            import datetime
            try:
                target_date = datetime.datetime.strptime(selected_month_year, '%b %Y')
                target_year = target_date.year
                target_month = target_date.month
                
                tech_work_orders = tech_work_orders[
                    (tech_work_orders['Year'] == target_year) & 
                    (tech_work_orders['Month'] == target_month)
                ]
            except:
                # If parsing fails, try direct comparison with Month Year column
                if "Month Year" in tech_work_orders.columns:
                    tech_work_orders = tech_work_orders[tech_work_orders["Month Year"] == selected_month_year]
    
    # Get unique work orders with their details
    unique_work_orders = tech_work_orders[["Work Order", "Description", "WO Type", "Site "]].drop_duplicates(subset=["Work Order"])
    
    wo_options = ["-- Select Work Order --"]
    wo_mapping = {}
    
    for _, row in unique_work_orders.iterrows():
        work_order = row["Work Order"]
        description = row["Description"]
        wo_type = row["WO Type"]
        site = row["Site "]
        
        display_wo = f"{work_order} - {site} ({wo_type})"
        wo_options.append(display_wo)
        wo_mapping[display_wo] = work_order
    
    return wo_options, wo_mapping

def get_work_date_options(selected_tech: str, cutlass_df: pd.DataFrame, selected_month_year: str = None, selected_work_order: str = None) -> Tuple[List[str], Dict[str, str]]:
    """
    Generate work date dropdown options for selected technician and work order
    
    Args:
        selected_tech: Selected technician name
        cutlass_df: Cutlass time entry dataframe
        selected_month_year: Selected month year filter (optional)
        selected_work_order: Selected work order (optional)
        
    Returns:
        Tuple of (work_date_options_list, work_date_mapping_dict)
    """
    # Filter by technician
    tech_work = cutlass_df[cutlass_df["User Resource: Full Name"] == selected_tech]
    
    # Apply month/year filter if provided
    if selected_month_year:
        tech_work = tech_work[tech_work["Month Year"] == selected_month_year]
    
    # Apply work order filter if provided
    if selected_work_order:
        tech_work = tech_work[tech_work["Work Order"] == selected_work_order]
    
    # Get unique work dates
    work_dates = tech_work["Work Date"].dropna().unique()
    work_dates = sorted(work_dates)
    
    work_date_options = ["-- Select Work Date --"] + [str(date) for date in work_dates]
    work_date_mapping = {"-- Select Work Date --": None}
    
    for date in work_dates:
        date_str = str(date)
        work_date_mapping[date_str] = date_str
    
    return work_date_options, work_date_mapping

def get_work_order_details(work_order_id: str, cutlass_df: pd.DataFrame, selected_tech: str, selected_month_year: str, selected_work_date: str) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:
    """
    Get detailed information for a specific work order from Cutlass data
    
    Args:
        work_order_id: Work order ID
        cutlass_df: Cutlass time entry dataframe
        
    Returns:
        Tuple of (work_order_details, asset_details) or (None, None) if not found
    """
    try:
        # Filter by work order and technician
        filtered_df = cutlass_df[(cutlass_df["Work Order"] == work_order_id) & (cutlass_df["User Resource: Full Name"] == selected_tech)& (cutlass_df["Work Date"] == selected_work_date)]
        
        # Apply month/year filter if provided
        if selected_month_year:
            filtered_df = filtered_df[filtered_df["Month Year"] == selected_month_year]
        
        wo_details = filtered_df.iloc[0]
        
        # Create asset details from available columns
        asset_details = {
            "AssetType": wo_details.get("Asset Description", "N/A"),
            "Manufacturer": "N/A",  # Not available in Cutlass data
            "Site": wo_details.get("Site ", "N/A"),
            "Plant": wo_details.get("Plant", "N/A")
        }
        asset_series = pd.Series(asset_details)
        
        return wo_details, asset_series
    except (IndexError, KeyError):
        return None, None

def get_technician_statistics(selected_tech: str, cutlass_df: pd.DataFrame) -> Dict[str, int]:
    """
    Get statistics for a selected technician from Cutlass data
    
    Args:
        selected_tech: Selected technician name
        cutlass_df: Cutlass time entry dataframe
        
    Returns:
        Dictionary with statistics
    """
    tech_work = cutlass_df[cutlass_df["User Resource: Full Name"] == selected_tech]
    
    total_assigned = len(tech_work["Work Order"].unique())
    total_hours = tech_work["Total Labor Hours"].sum()
    corrective_work = len(tech_work[tech_work["WO Type"] == "Corrective"])
    
    return {
        "total_assigned": total_assigned,
        "total_hours": round(total_hours, 1),
        "corrective_work": corrective_work,
        "technician_name": selected_tech
    }

def get_global_statistics(cutlass_df: pd.DataFrame) -> Dict[str, int]:
    """
    Get global statistics across all Cutlass data
    
    Args:
        cutlass_df: Cutlass time entry dataframe
        
    Returns:
        Dictionary with global statistics
    """
    return {
        "total_work_orders": cutlass_df["Work Order"].nunique(),
        "total_entries": len(cutlass_df),
        "total_technicians": cutlass_df["User Resource: Full Name"].nunique(),
        "total_hours": round(cutlass_df["Total Labor Hours"].sum(), 1)
    }

def get_technician_work_orders(selected_tech: str, cutlass_df: pd.DataFrame) -> pd.DataFrame:
    """
    Get work orders for a specific technician from Cutlass data
    
    Args:
        selected_tech: Selected technician name
        cutlass_df: Cutlass time entry dataframe
        
    Returns:
        DataFrame with work order details for the technician
    """
    tech_work = cutlass_df[cutlass_df["User Resource: Full Name"] == selected_tech]
    
    # Group by work order to show unique work orders with aggregated data
    display_assigned = tech_work.groupby("Work Order").agg({
        "Description": "first",
        "WO Type": "first", 
        "Site ": "first",
        "Work Date": "first",
        "Total Labor Hours": "sum"
    }).reset_index()
    
    return display_assigned[["Work Order", "Description", "Site ", "WO Type", "Work Date", "Total Labor Hours"]]

def get_work_order_completion_notes(dataframe: pd.DataFrame, work_order: str, selected_tech: str, selected_month_year: str, selected_work_date: str) -> str:
    """
    Get completion notes for a specific work order from the original dataset
    
    Args:
        dataframe: DataFrame to search in
        work_order_id: Work order ID to find completion notes for
        selected_tech: Technician name
        selected_month_year: Month year filter
        selected_work_date: Work date filter
        
    Returns:
        Completion notes for the work order (first non-empty occurrence)
    """
    try:
        # Filter data based on all criteria
        work_order_data = dataframe[
            (dataframe["Work Order"] == work_order) & 
            (dataframe["User Resource: Full Name"] == selected_tech) & 
            (dataframe["Month Year"] == selected_month_year) & 
            (dataframe["Work Date"] == selected_work_date)
        ]
        if len(work_order_data) > 0:
            # Get all completion notes for this work order and concatenate them
            completion_notes = work_order_data["Completion Notes"].dropna()
            if len(completion_notes) > 0:
                # Join all completion notes with double line breaks if multiple entries
                full_notes = "\n\n".join([str(note).strip() for note in completion_notes if str(note).strip()])
                return full_notes
            else:
                return "No completion notes available for this work order."
        else:
            return "Work order not found for this technician and date."
    except Exception as e:
        return "No completion notes available for this work order."

def get_time_type(cutlass_df: pd.DataFrame, work_order: str, selected_tech: str, selected_month_year: str, selected_work_date: str) -> str:
    """
    Get the Time Type for a specific work order from the dataset
    
    Args:
        cutlass_df: Cutlass time entry dataframe
        work_order: Work order ID
        selected_tech: Technician name
        selected_month_year: Month year filter
        selected_work_date: Work date filter
        
    Returns:
        Time Type for the work order (e.g., "Work", "Training", "Warranty Support")
    """
    try:
        # Filter data based on all criteria
        work_order_data = cutlass_df[
            (cutlass_df["Work Order"] == work_order) & 
            (cutlass_df["User Resource: Full Name"] == selected_tech) & 
            (cutlass_df["Month Year"] == selected_month_year) & 
            (cutlass_df["Work Date"] == selected_work_date)
        ]
        
        if len(work_order_data) > 0:
            # Get the Time Type from the first matching row
            time_type = work_order_data["Time Type"].iloc[0]
            if pd.notna(time_type):
                return str(time_type)
            else:
                return "Work"  # Default fallback
        else:
            return "Work"  # Default fallback
    except Exception as e:
        return "Work"  # Default fallback



def get_suggested_labor_hours(cutlass_df: pd.DataFrame, wo_type: str = None, description: str = None) -> float:
    """
    Get suggested total labor hours based on similar work orders
    
    Args:
        cutlass_df: Cutlass time entry dataframe
        wo_type: Work order type filter (optional)
        description: Work order description filter (optional)
        
    Returns:
        Suggested total labor hours (average)
    """
    filtered_df = cutlass_df.copy()
    
    # Filter by WO Type if provided
    if wo_type:
        filtered_df = filtered_df[filtered_df["WO Type"] == wo_type]
    
    # Filter by similar description if provided (contains key words)
    if description:
        # Extract key words from description (simple approach)
        key_words = [word.lower() for word in description.split() if len(word) > 3]
        if key_words:
            # Escape special regex characters and join with OR
            escaped_words = [re.escape(word) for word in key_words]
            pattern = '|'.join(escaped_words)
            mask = filtered_df["Description"].str.lower().str.contains(pattern, na=False, regex=True)
            similar_work = filtered_df[mask]
            if len(similar_work) > 0:
                filtered_df = similar_work
    
    # Calculate average total labor hours
    if len(filtered_df) > 0:
        avg_hours = filtered_df["Total Labor Hours"].mean()
        return round(avg_hours, 1)
    else:
        return 8.0  # Default fallback 