import os
import pickle
import time
import requests
from datetime import datetime
from statistics import median

data = {}  # Key = tx hash, val = dict(transaction metadata)
NETWORK = "testnet"
API_URL = "https://community.rino.io/explorer/" + NETWORK + "/api"


def enrich_data():
    global data
    for tx_hash in data.keys():
        #try:
            tx_response = requests.get(API_URL + "/transaction/" + str(tx_hash)).json()["data"]
            block_response = requests.get(API_URL + "/block/" + str(tx_response["block_height"])).json()["data"]
            previous_block_response = requests.get(API_URL + "/block/" + str(int(tx_response["block_height"]) - 1)).json()["data"]
            data[tx_hash]['Tx_Size'] = tx_response["tx_size"]
            # Check if the fee is missing
            if 'Tx_Fee' not in data[tx_hash].keys():
                data[tx_hash]['Tx_Fee'] = float(tx_response['tx_fee'] * 0.000000000001) #  Converted from piconero to monero
            data[tx_hash]['Tx_Fee_Per_Byte'] = float(data[tx_hash]['Tx_Fee']) / int(data[tx_hash]['Tx_Size'])
            data[tx_hash]['Num_Confirmations'] = tx_response["confirmations"]
            data[tx_hash]['Time_Of_Enrichment'] = int(time.time())
            if tx_response["coinbase"] == "false":
                data[tx_hash]['Is_Coinbase_Tx'] = False
            elif tx_response["coinbase"] == "true":
                data[tx_hash]['Is_Coinbase_Tx'] = True
            data[tx_hash]['Tx_Extra'] = tx_response["extra"]
            data[tx_hash]['Ring_CT_Type'] = tx_response["rct_type"]
            data[tx_hash]['Payment_ID'] = tx_response["payment_id"]
            data[tx_hash]['Payment_ID8'] = tx_response["payment_id8"]

            Total_Block_Tx_Fees = 0
            for tx in block_response["txs"]:
                Total_Block_Tx_Fees += int(tx["tx_fee"])
            data[tx_hash]['Total_Block_Tx_Fees'] = float(Total_Block_Tx_Fees * 0.000000000001) #  Converted from piconero to monero
            data[tx_hash]['Block_Size'] = block_response["size"]
            data[tx_hash]['Time_Since_Last_Block'] = int((datetime.fromtimestamp(int(block_response["timestamp"])) - datetime.fromtimestamp(int(previous_block_response["timestamp"]))).total_seconds())

            #  Add Output Information
            for output_idx, output in enumerate(tx_response['outputs']):
                data[tx_hash]['Outputs']['Output_Data'].append({'Amount': output['amount'], 'Stealth_Address': output['public_key']})
            for Decoy in data[tx_hash]['Outputs']['Decoys_On_Chain']:
                #  Add Temporal Features for the decoy ( This takes up a ton of time )
                #  Retrieve the transaction information about the decoy ring signatures
                decoy_tx_response = requests.get(API_URL + "/transaction/" + str(Decoy['Tx_Hash'])).json()["data"]
                #  Iterate through each input
                for decoy_input in decoy_tx_response['inputs']:
                    #  Create an entry for the temporal data
                    Decoy['Time_Deltas_Between_Ring_Members'] = {}
                    #  Make sure there is at least 1 mixin
                    if len(decoy_input['mixins']) != 0:
                        #  A place to store the block times of each ring member
                        Ring_Member_Times = []
                        #  Iterate through each mixin, add it to the list and calculate the time deltas
                        for member_idx, each_member in enumerate(decoy_input['mixins']):
                            Ring_Member_Times.append(requests.get(API_URL + "/block/" + str(each_member['block_no'])).json()['data']['timestamp'])
                            #  If the list has at least 2 items
                            if len(Ring_Member_Times) > 1:
                                time_delta = int((datetime.fromtimestamp(Ring_Member_Times[member_idx]) - datetime.fromtimestamp(Ring_Member_Times[member_idx - 1])).total_seconds())
                                Decoy['Time_Deltas_Between_Ring_Members'][str(member_idx - 1) + '_' + str(member_idx)] = time_delta
                                # Add temporal features
                                Decoy['Time_Deltas_Between_Ring_Members']['Total_Decoy_Time_Span'] = int((datetime.fromtimestamp(Ring_Member_Times[len(Ring_Member_Times) - 1]) - datetime.fromtimestamp(Ring_Member_Times[0])).total_seconds())
                                Decoy['Time_Deltas_Between_Ring_Members']['Time_Delta_From_Newest_Ring_To_Block'] = int((datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch']) - datetime.fromtimestamp(Ring_Member_Times[len(Ring_Member_Times) - 1])).total_seconds())
                                Decoy['Time_Deltas_Between_Ring_Members']['Time_Delta_From_Oldest_Ring_To_Block'] = int((datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch']) - datetime.fromtimestamp(Ring_Member_Times[0])).total_seconds())
                                Decoy['Time_Deltas_Between_Ring_Members']['Mean_Ring_Time'] = sum(Ring_Member_Times) / len(Ring_Member_Times)
                                Decoy['Time_Deltas_Between_Ring_Members']['Median_Ring_Time'] = int(median(Ring_Member_Times))

            #  Add Input Information
            for input in tx_response['inputs']:
                data[tx_hash]['Inputs'].append(
                    {
                        'Amount': input['amount'],
                        'Key_Image': input['key_image'],
                        'Ring_Members': input['mixins']
                    }
                )
            data[tx_hash]['Num_Inputs'] = len(data[tx_hash]['Inputs'])
            data[tx_hash]['Num_Outputs'] = len(data[tx_hash]['Outputs']['Output_Data'])
            data[tx_hash]['Num_Decoys'] = len(data[tx_hash]['Outputs']['Decoys_On_Chain'])
            data[tx_hash]['Block_To_xmr2csv_Time_Delta'] = int((datetime.fromtimestamp(data[tx_hash]['xmr2csv_Data_Collection_Time']) - datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch'])).total_seconds())
            # Temporal Features

            if len(data[tx_hash]['Inputs']) != 0:
                for input_idx, each_input in enumerate(data[tx_hash]['Inputs']):
                    data[tx_hash]['Inputs'][input_idx]['Time_Deltas_Between_Ring_Members'] = {}
                    #  A place to store the block times of each ring member
                    ring_mem_times = []
                    if len(each_input['Ring_Members']) != 0:
                        for ring_num, ring_mem in enumerate(each_input['Ring_Members']):
                            ring_mem_times.append(requests.get(API_URL + "/block/" + str(ring_mem['block_no'])).json()['data']['timestamp'])
                            #  If the list has at least 2 items
                            if len(ring_mem_times) > 1:
                                time_delta = int((datetime.fromtimestamp(ring_mem_times[ring_num]) - datetime.fromtimestamp(ring_mem_times[ring_num - 1])).total_seconds())
                                data[tx_hash]['Inputs'][input_idx]['Time_Deltas_Between_Ring_Members'][str(ring_num-1) + '_' + str(ring_num)] = time_delta
                    if len(ring_mem_times) > 1:
                        # Add temporal features
                        data[tx_hash]['Inputs'][input_idx]['Total_Ring_Time_Span'] = int((datetime.fromtimestamp(ring_mem_times[len(ring_mem_times)-1]) - datetime.fromtimestamp(ring_mem_times[0])).total_seconds())
                        data[tx_hash]['Inputs'][input_idx]['Time_Delta_From_Newest_Ring_To_Block'] = int((datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch']) - datetime.fromtimestamp(ring_mem_times[len(ring_mem_times)-1])).total_seconds())
                        data[tx_hash]['Inputs'][input_idx]['Time_Delta_From_Oldest_Ring_To_Block'] = int((datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch']) - datetime.fromtimestamp(ring_mem_times[0])).total_seconds())
                        data[tx_hash]['Inputs'][input_idx]['Mean_Ring_Time'] = sum(ring_mem_times) / len(ring_mem_times)
                        data[tx_hash]['Inputs'][input_idx]['Median_Ring_Time'] = int(median(ring_mem_times))
                    data[tx_hash]['Inputs'][input_idx]['Ring_Member_Block_Time_Stamps'] = ring_mem_times

            #  Temporal features for decoys on chain
            data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain'] = {}
            if len(data[tx_hash]['Outputs']['Decoys_On_Chain']) != 0:
                #  A place to store the block times of each ring member
                decoys_on_chain_times = []
                for member_idx, each_member in enumerate(data[tx_hash]['Outputs']['Decoys_On_Chain']):
                    decoys_on_chain_times.append(requests.get(API_URL + "/block/" + str(each_member['Block_Number'])).json()['data']['timestamp'])
                    #  If the list has at least 2 items
                    if len(decoys_on_chain_times) > 1:
                        time_delta = int((datetime.fromtimestamp(decoys_on_chain_times[member_idx]) - datetime.fromtimestamp(decoys_on_chain_times[member_idx - 1])).total_seconds())
                        data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain'][str(member_idx-1) + '_' + str(member_idx)] = time_delta
                        # Add temporal features
                        data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Total_Decoy_Time_Span'] = int((datetime.fromtimestamp(decoys_on_chain_times[len(decoys_on_chain_times)-1]) - datetime.fromtimestamp(decoys_on_chain_times[0])).total_seconds())
                        data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Time_Delta_From_Newest_Decoy_To_Block'] = int((datetime.fromtimestamp(decoys_on_chain_times[len(decoys_on_chain_times)-1]) - datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch'])).total_seconds())
                        data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Time_Delta_From_Oldest_Decoy_To_Block'] = int((datetime.fromtimestamp(decoys_on_chain_times[0]) - datetime.fromtimestamp(data[tx_hash]['Block_Timestamp_Epoch'])).total_seconds())
                        data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Mean_Decoy_Time'] = sum(decoys_on_chain_times) / len(decoys_on_chain_times)
                        data[tx_hash]['Outputs']['Time_Deltas_Between_Decoys_On_Chain']['Median_Decoy_Time'] = int(median(decoys_on_chain_times))
            pass
        # except Exception as e:
        #     print(e)


def combine_files(Wallet_addrs):
    #  Most function calls will input a list of 2 wallet addresses
    for addr in Wallet_addrs:
        with open("./cli_export_" + addr + ".csv", "r") as fp:
            next(fp)  # Skip header of csv
            for line in fp:
                cli_csv_values = line.split(",")
                if cli_csv_values[1].strip() == "out":  # Only add outgoing transactions to the dataset
                    transaction = {}
                    transaction['Block_Number'] = int(cli_csv_values[0].strip())
                    transaction['Direction'] = cli_csv_values[1].strip()
                    transaction['Block_Timestamp'] = cli_csv_values[3].strip()
                    # Convert timestamp to epoch time
                    p = "%Y-%m-%d %H:%M:%S"
                    epoch = datetime(1970, 1, 1)
                    transaction['Block_Timestamp_Epoch'] = int((datetime.strptime(transaction['Block_Timestamp'].strip(), p) - epoch).total_seconds())

                    transaction['Amount'] = float(cli_csv_values[4].strip())
                    transaction['Wallet_Balance'] = float(cli_csv_values[5].strip())
                    transaction['Tx_Fee'] = float(cli_csv_values[8].strip())
                    transaction['Destination_Address'] = cli_csv_values[9].strip()
                    transaction['Sender_Address'] = addr
                    transaction['Network'] = NETWORK

                    transaction['Outputs'] = {}
                    transaction['Outputs']['Output_Data'] = list()
                    transaction['Inputs'] = []

                    with open("./xmr2csv_start_time_" + addr + ".csv", "r") as fp2:
                        for line2 in fp2:
                            transaction['xmr2csv_Data_Collection_Time'] = int(line2.strip())
                            break
                    #  Check if the hash is a key in the dataset
                    if cli_csv_values[6].strip() not in data:
                        data[cli_csv_values[6].strip()] = transaction

        with open("./xmr_report_" + addr + ".csv", "r") as fp:
            next(fp)  # Skip header of csv
            for line in fp:
                xmr2csv_report_csv_values = line.split(",")
                tx_hash = xmr2csv_report_csv_values[2].strip()
                #  Check if the tx hash is in the dataset yet
                if xmr2csv_report_csv_values[2].strip() in data:
                    data[tx_hash]['Tx_Version'] = xmr2csv_report_csv_values[4].strip()
                    data[tx_hash]['Tx_Public_Key'] = xmr2csv_report_csv_values[3].strip()
                    data[tx_hash]['Output_Pub_Key'] = xmr2csv_report_csv_values[8].strip()
                    data[tx_hash]['Output_Key_Img'] = xmr2csv_report_csv_values[9].strip()
                    data[tx_hash]['Out_idx'] = int(xmr2csv_report_csv_values[6].strip())
                    data[tx_hash]['Output_Number_Spent'] = int(xmr2csv_report_csv_values[10].strip())

                    #  Open the file that has the timestamp from when the data was collected
                    with open("./xmr2csv_start_time_" + addr + ".csv", "r") as fp2:
                        for line2 in fp2:
                            data[tx_hash]['xmr2csv_Data_Collection_Time'] = int(line2.strip())
                            break

                    #  Search through the export of all ring member occurrences on chain to see if our output public key was used
                    data[tx_hash]['Outputs']['Decoys_On_Chain'] = []
                    with open("./xmr_report_ring_members_" + addr + ".csv", "r") as fp2:
                        next(fp2)  # Skip header of csv
                        for line2 in fp2:
                            ring_members_csv_values = line2.split(",")
                            Ring_Member = {}
                            #  Make sure the ring members public key matches the current public key
                            if data[tx_hash]['Output_Pub_Key'] == ring_members_csv_values[3].strip():
                                Ring_Member['Block_Number'] = int(ring_members_csv_values[1].strip())
                                # Convert timestamp to epoch time before saving
                                p = "%Y-%m-%d %H:%M:%S"
                                epoch = datetime(1970, 1, 1)
                                ring_member_epoch_time = int((datetime.strptime(ring_members_csv_values[0].strip(), p) - epoch).total_seconds())
                                Ring_Member['Block_Timestamp'] = ring_member_epoch_time
                                Ring_Member['Key_image'] = ring_members_csv_values[4].strip()
                                Ring_Member['Tx_Hash'] = ring_members_csv_values[2].strip()
                                Ring_Member['Ring_no/Ring_size'] = ring_members_csv_values[5].strip()
                                #  Find the relative age of the outputs public key on the chain compared to when xmr2csv was ran
                                #  https://stackoverflow.com/questions/30468371/how-to-convert-python-timestamp-string-to-epoch

                                #  The time from when the data was collected minus the decoy block timestamp
                                Ring_Member['Ring_Member_Relative_Age'] = int((datetime.fromtimestamp(data[tx_hash]['xmr2csv_Data_Collection_Time']) - datetime.fromtimestamp(Ring_Member['Block_Timestamp'])).total_seconds())
                                #  Open the frequency file
                                with open("./xmr_report_ring_members_freq_" + addr + ".csv", "r") as fp3:
                                    next(fp3)  # Skip header of csv
                                    for line3 in fp3:
                                        ring_member_freq_csv_values = line3.split(",")
                                        #  Check if the ring members public key matches the current public key
                                        if data[tx_hash]['Output_Pub_Key'] == ring_member_freq_csv_values[0].strip():
                                            #  Add the amount of times it has been seen on chain
                                            Ring_Member['Ring_Member_Freq'] = int(ring_member_freq_csv_values[1].strip())
                                data[tx_hash]['Outputs']['Decoys_On_Chain'].append(Ring_Member)

        with open("./xmr_report_outgoing_txs_" + addr + ".csv", "r") as fp:
            next(fp)  # Skip header of csv
            for line in fp:
                xmr2csv_outgoing_csv_values = line.split(",")
                if xmr2csv_outgoing_csv_values[2].strip() in data:
                    data[xmr2csv_outgoing_csv_values[2].strip()]['Ring_no/Ring_size'] = xmr2csv_outgoing_csv_values[5].strip()
                else:
                    transaction = {}
                    transaction['Block_Timestamp'] = xmr2csv_outgoing_csv_values[0].strip()
                    transaction['Block_Number'] = xmr2csv_outgoing_csv_values[1].strip()
                    transaction['Output_Pub_Key'] = xmr2csv_outgoing_csv_values[3].strip()
                    transaction['Output_Key_Img'] = xmr2csv_outgoing_csv_values[4].strip()
                    transaction['Ring_no/Ring_size'] = xmr2csv_outgoing_csv_values[5].strip()
                    with open("./xmr2csv_start_time_" + addr + ".csv", "r") as fp2:
                        for line2 in fp2:
                            transaction['xmr2csv_Data_Collection_Time'] = int(line2.strip())
                            break
                    data[xmr2csv_outgoing_csv_values[2].strip()] = transaction


def discover_wallet_directories(dir_to_search):
    # traverse root directory, and list directories as dirs and files as files
    unique_directories = []
    for root, dirs, files in os.walk(dir_to_search):
        for name in files:
            #  Find all csv files
            if name.lower().endswith(".csv"):
                #  Find all the unique folders holding csv files
                if root not in unique_directories:
                    unique_directories.append(root)
    cwd = os.getcwd()  # Set a starting directory
    #  Go through each directory that has csv files in it
    for idx, dir in enumerate(unique_directories):
        os.chdir(dir)
        Wallet_addrs = []
        for root, dirs, files in os.walk("."):
            for name in files:
                #  Get each csv file
                if name.lower().endswith(".csv"):
                    #  Extract the 2 unique wallet addr from the name of the files
                    addr = name[::-1].split(".")[1].split("_")[0][::-1]
                    if addr not in Wallet_addrs:
                        Wallet_addrs.append(addr)
                    #  Dont keep looking if the two wallet addresses are already found
                    if len(Wallet_addrs) == 2:
                        break
        #  Once the two wallet addr are found send the list to combine the files
        combine_files(Wallet_addrs)
        os.chdir(cwd)


def main():
    discover_wallet_directories("./Wallets/1")
    enrich_data()
    global data
    with open("data.pkl", "wb") as fp:
        pickle.dump(data, fp)

    # with open("data.pkl", "rb") as fp:
    #     data = pickle.load(fp)
    # pass


if __name__ == '__main__':
    main()
