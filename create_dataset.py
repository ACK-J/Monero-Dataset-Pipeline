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
    for txid in data.keys():
        try:
            tx_response = requests.get(API_URL + "/transaction/" + str(txid)).json()["data"]
            block_response = requests.get(API_URL + "/block/" + str(tx_response["block_height"])).json()["data"]
            previous_block_response = requests.get(API_URL + "/block/" + str(int(tx_response["block_height"]) - 1)).json()["data"]
            data[txid]['Tx_Size'] = tx_response["tx_size"]
            # Check if the fee is missing
            if 'Tx_Fee' not in data[txid].keys():
                data[txid]['Tx_Fee'] = float(tx_response['tx_fee'] * 0.000000000001) #  Converted from piconero to monero
            data[txid]['Tx_Fee_Per_Byte'] = float(data[txid]['Tx_Fee']) / int(data[txid]['Tx_Size'])
            data[txid]['Block_Timestamp_Epoch'] = tx_response["timestamp"]
            data[txid]['Num_Confirmations'] = tx_response["confirmations"]
            data[txid]['Time_Of_Enrichment'] = int(time.time())
            if tx_response["coinbase"] == "false":
                data[txid]['Is_Coinbase_Tx'] = False
            elif tx_response["coinbase"] == "true":
                data[txid]['Is_Coinbase_Tx'] = True
            data[txid]['Tx_Extra'] = tx_response["extra"]
            data[txid]['Ring_CT_Type'] = tx_response["rct_type"]
            data[txid]['Payment_ID'] = tx_response["payment_id"]
            data[txid]['Payment_ID8'] = tx_response["payment_id8"]

            Total_Block_Tx_Fees = 0
            for tx in block_response["txs"]:
                Total_Block_Tx_Fees += int(tx["tx_fee"])
            data[txid]['Total_Block_Tx_Fees'] = float(Total_Block_Tx_Fees * 0.000000000001) #  Converted from piconero to monero
            data[txid]['Block_Size'] = block_response["size"]
            data[txid]['Time_Since_Last_Block'] = int((datetime.fromtimestamp(int(block_response["timestamp"])) - datetime.fromtimestamp(int(previous_block_response["timestamp"]))).total_seconds())

            #  Add Output Information
            data[txid]['Outputs'] = []
            for output in tx_response['outputs']:
                data[txid]['Outputs'].append({'Amount': output['amount'], 'Stealth_Address': output['public_key']})

            #  Add Input Information
            data[txid]['Inputs'] = []
            for input in tx_response['inputs']:
                data[txid]['Inputs'].append(
                    {
                        'Amount': input['amount'],
                        'Key_Image': input['key_image'],
                        'Ring_Members': input['mixins']
                    }
                )
            data[txid]['Num_Inputs'] = len(data[txid]['Inputs'])
            data[txid]['Num_Outputs'] = len(data[txid]['Outputs'])
            data[txid]['Num_Outputs'] = len(data[txid]['Decoys_On_Chain'])
            data[txid]['Block_To_xmr2csv_Time_Delta'] = int((datetime.fromtimestamp(data[txid]['xmr2csv_Data_Collection_Time']) - datetime.fromtimestamp(data[txid]['Block_Timestamp_Epoch'])).total_seconds())
            # Temporal Features

            if len(data[txid]['Inputs']) != 0:
                for input_idx, each_input in enumerate(data[txid]['Inputs']):
                    data[txid]['Inputs'][input_idx]['Time_Deltas_Between_Ring_Members'] = {}
                    #  A place to store the block times of each ring member
                    ring_mem_times = []
                    if len(each_input['Ring_Members']) != 0:
                        for ring_num, ring_mem in enumerate(each_input['Ring_Members']):
                            ring_mem_times.append(requests.get(API_URL + "/block/" + str(ring_mem['block_no'])).json()['data']['timestamp'])
                            #  If the list has at least 2 items
                            if len(ring_mem_times) > 1:
                                time_delta = int((datetime.fromtimestamp(ring_mem_times[ring_num]) - datetime.fromtimestamp(ring_mem_times[ring_num - 1])).total_seconds())
                                data[txid]['Inputs'][input_idx]['Time_Deltas_Between_Ring_Members'][str(ring_num-1) + '_' + str(ring_num)] = time_delta
                    if len(ring_mem_times) > 1:
                        # Add temporal features
                        data[txid]['Inputs'][input_idx]['Total_Ring_Time_Span'] = int((datetime.fromtimestamp(ring_mem_times[len(ring_mem_times)-1]) - datetime.fromtimestamp(ring_mem_times[0])).total_seconds())
                        data[txid]['Inputs'][input_idx]['Time_Delta_From_Newest_Ring_To_Block'] = int((datetime.fromtimestamp(data[txid]['Block_Timestamp_Epoch']) - datetime.fromtimestamp(ring_mem_times[len(ring_mem_times)-1])).total_seconds())
                        data[txid]['Inputs'][input_idx]['Time_Delta_From_Oldest_Ring_To_Block'] = int((datetime.fromtimestamp(data[txid]['Block_Timestamp_Epoch']) - datetime.fromtimestamp(ring_mem_times[0])).total_seconds())
                        data[txid]['Inputs'][input_idx]['Mean_Ring_Time'] = sum(ring_mem_times) / len(ring_mem_times)
                        data[txid]['Inputs'][input_idx]['Median_Ring_Time'] = int(median(ring_mem_times))
                    data[txid]['Inputs'][input_idx]['Ring_Member_Block_Time_Stamps'] = ring_mem_times

            #  Temporal features for decoys on chain
            data[txid]['Time_Deltas_Between_Decoys_On_Chain'] = {}
            if len(data[txid]['Decoys_On_Chain']) != 0:
                #  A place to store the block times of each ring member
                decoys_on_chain_times = []
                for member_idx, each_member in enumerate(data[txid]['Decoys_On_Chain']):
                    decoys_on_chain_times.append(requests.get(API_URL + "/block/" + str(each_member['Block_Number'])).json()['data']['timestamp'])
                    #  If the list has at least 2 items
                    if len(decoys_on_chain_times) > 1:
                        time_delta = int((datetime.fromtimestamp(decoys_on_chain_times[member_idx]) - datetime.fromtimestamp(decoys_on_chain_times[member_idx - 1])).total_seconds())
                        data[txid]['Time_Deltas_Between_Decoys_On_Chain'][str(member_idx-1) + '_' + str(member_idx)] = time_delta
                        # Add temporal features
                        data[txid]['Time_Deltas_Between_Decoys_On_Chain']['Total_Decoy_Time_Span'] = int((datetime.fromtimestamp(decoys_on_chain_times[len(decoys_on_chain_times)-1]) - datetime.fromtimestamp(decoys_on_chain_times[0])).total_seconds())
                        data[txid]['Time_Deltas_Between_Decoys_On_Chain']['Time_Delta_From_Newest_Decoy_To_Block'] = int((datetime.fromtimestamp(decoys_on_chain_times[len(decoys_on_chain_times)-1]) - datetime.fromtimestamp(data[txid]['Block_Timestamp_Epoch'])).total_seconds())
                        data[txid]['Time_Deltas_Between_Decoys_On_Chain']['Time_Delta_From_Oldest_Decoy_To_Block'] = int((datetime.fromtimestamp(decoys_on_chain_times[0]) - datetime.fromtimestamp(data[txid]['Block_Timestamp_Epoch'])).total_seconds())
                        data[txid]['Time_Deltas_Between_Decoys_On_Chain']['Mean_Decoy_Time'] = sum(decoys_on_chain_times) / len(decoys_on_chain_times)
                        data[txid]['Time_Deltas_Between_Decoys_On_Chain']['Median_Decoy_Time'] = int(median(decoys_on_chain_times))
            pass
        except Exception as e:
            print(e)


def combine_files(Wallet_addrs):
    #  Most function calls will input a list of 2 wallet addresses
    for addr in Wallet_addrs:
        with open("./cli_export_" + addr + ".csv", "r") as fp:
            next(fp)  # Skip header of csv
            for line in fp:
                cli_csv_values = line.split(",")
                if cli_csv_values[1].strip() == "out": #  Only add outgoing transactions to the dataset
                    transaction = {}
                    transaction['Block_Number'] = int(cli_csv_values[0].strip())
                    transaction['Direction'] = cli_csv_values[1].strip()
                    transaction['Block_Timestamp'] = cli_csv_values[3].strip()
                    transaction['Amount'] = float(cli_csv_values[4].strip())
                    transaction['Wallet_Balance'] = float(cli_csv_values[5].strip())
                    transaction['Tx_Fee'] = float(cli_csv_values[8].strip())
                    transaction['Destination_Address'] = cli_csv_values[9].strip()
                    transaction['Network'] = NETWORK

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
                #  Check if the tx hash is in the dataset yet
                if xmr2csv_report_csv_values[2].strip() in data:
                    data[xmr2csv_report_csv_values[2].strip()]['Tx_Version'] = xmr2csv_report_csv_values[4].strip()
                    data[xmr2csv_report_csv_values[2].strip()]['Tx_Public_Key'] = xmr2csv_report_csv_values[3].strip()
                    data[xmr2csv_report_csv_values[2].strip()]['Output_Pub_Key'] = xmr2csv_report_csv_values[8].strip()
                    data[xmr2csv_report_csv_values[2].strip()]['Output_Key_Img'] = xmr2csv_report_csv_values[9].strip()
                    data[xmr2csv_report_csv_values[2].strip()]['Output_Number_Spent'] = xmr2csv_report_csv_values[10].strip()

                    #  Search through the export of all ring member occurrences on chain to see if our output public key was used
                    data[xmr2csv_report_csv_values[2].strip()]['Decoys_On_Chain'] = []
                    with open("./xmr_report_ring_members_" + addr + ".csv", "r") as fp2:
                        next(fp2)  # Skip header of csv
                        for line2 in fp2:
                            ring_members_csv_values = line2.split(",")
                            Ring_Member = {}
                            #  Make sure the ring members public key matches the current public key
                            if data[xmr2csv_report_csv_values[2].strip()]['Output_Pub_Key'] == ring_members_csv_values[3].strip():
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
                                Ring_Member['Ring_Member_Relative_Age'] = int((datetime.fromtimestamp(data[xmr2csv_report_csv_values[2].strip()]['xmr2csv_Data_Collection_Time']) - datetime.fromtimestamp(Ring_Member['Block_Timestamp'])).total_seconds())
                                with open("./xmr_report_ring_members_freq_" + addr + ".csv", "r") as fp3:
                                    next(fp3)  # Skip header of csv
                                    for line3 in fp3:
                                        ring_member_freq_csv_values = line3.split(",")
                                        #  Check if the ring members public key matches the current public key
                                        if data[xmr2csv_report_csv_values[2].strip()]['Output_Pub_Key'] == ring_member_freq_csv_values[0].strip():
                                            #  Add the amount of times it has been seen on chain
                                            Ring_Member['Ring_Member_Freq'] = int(ring_member_freq_csv_values[1].strip())
                                data[xmr2csv_report_csv_values[2].strip()]['Decoys_On_Chain'].append(Ring_Member)

                    with open("./xmr2csv_start_time_" + addr + ".csv", "r") as fp2:
                        for line2 in fp2:
                            data[xmr2csv_report_csv_values[2].strip()]['xmr2csv_Data_Collection_Time'] = int(line2.strip())
                            break

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


def discover_wallet_directories():
    # traverse root directory, and list directories as dirs and files as files
    unique_directories = []
    for root, dirs, files in os.walk("./Wallets"):
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
    discover_wallet_directories()
    enrich_data()
    global data
    with open("data.pkl", "wb") as fp:
        pickle.dump(data, fp)

    # with open("data.pkl", "rb") as fp:
    #     data = pickle.load(fp)
    # pass


if __name__ == '__main__':
    main()
