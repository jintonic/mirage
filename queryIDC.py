import sys
import warnings
import idc_index

warnings.simplefilter(action='ignore', category=FutureWarning)

def main():
    if len(sys.argv) < 2:
        print("Usage: python queryIDC.py <body_part>")
        return

    target_region = sys.argv[1].upper()
    client = idc_index.IDCClient()

    # Using only the confirmed columns from your error message
    query = f"""
    SELECT 
        PatientID, 
        SeriesInstanceUID, 
        BodyPartExamined, 
        SeriesDescription,
        PatientSex,
        PatientAge
    FROM 
        index
    WHERE 
        Modality = 'CT' 
        AND BodyPartExamined = '{target_region}'
    LIMIT 10
    """

    print(f"--- Searching IDC for: {target_region} ---")
    
    try:
        results = client.sql_query(query)
        if results.empty:
            print(f"No results found for '{target_region}'.")
        else:
            print(results)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()