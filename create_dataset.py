import os
import pickle
import time
import requests
from datetime import datetime

# TODO add checkpoint saves
# TODO add tx inputs and decoy info
# TODO timestamps cant be subtracted need to use a library

# Key = tx hash, val = dict(transaction metadata)
data = {}
NETWORK = "testnet"
API_URL = "https://community.rino.io/explorer/" + NETWORK + "/api"


def enrich_data():
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
            data[txid]['Tx_Timestamp_Epoch'] = tx_response["timestamp"]
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

            total_block_fee = 0
            for tx in block_response["txs"]:
                total_block_fee += int(tx["tx_fee"])
            data[txid]['Total_Block_Fee'] = float(total_block_fee * 0.000000000001) #  Converted from piconero to monero
            data[txid]['Block_Size'] = block_response["size"]
            data[txid]['Time_Since_Last_Block'] = int(block_response["timestamp"]) - int(previous_block_response["timestamp"])

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
                        'Mixins': input['mixins']
                    }
                )
            data[txid]['Num_Inputs'] = len(data[txid]['Inputs'])
            data[txid]['Num_Outputs'] = len(data[txid]['Outputs'])
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
                    transaction['Tx_Timestamp'] = cli_csv_values[3].strip()
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
                    data[xmr2csv_report_csv_values[2].strip()]['Ring_Members_OnChain'] = []
                    with open("./xmr_report_ring_members_" + addr + ".csv", "r") as fp2:
                        next(fp2)  # Skip header of csv
                        for line2 in fp2:
                            ring_members_csv_values = line2.split(",")
                            Ring_Member = {}
                            #  Make sure the ring members public key matches the current public key
                            if data[xmr2csv_report_csv_values[2].strip()]['Output_Pub_Key'] == ring_members_csv_values[3].strip():
                                Ring_Member['Block_Number'] = ring_members_csv_values[1].strip()
                                # Convert timestamp to epoch time before saving
                                p = "%Y-%m-%d %H:%M:%S"
                                epoch = datetime(1970, 1, 1)
                                ring_member_epoch_time = int((datetime.strptime(ring_members_csv_values[0].strip(), p) - epoch).total_seconds())
                                Ring_Member['Tx_Timestamp'] = ring_member_epoch_time
                                Ring_Member['Key_image'] = ring_members_csv_values[4].strip()
                                Ring_Member['Ring_no/Ring_size'] = ring_members_csv_values[5].strip()
                                #  Find the relative age of the outputs public key on the chain compared to when xmr2csv was ran
                                #  https://stackoverflow.com/questions/30468371/how-to-convert-python-timestamp-string-to-epoch
                                Ring_Member['Ring_Member_Relative_Age'] = data[xmr2csv_report_csv_values[2].strip()]['xmr2csv_Data_Collection_Time'] - Ring_Member['Tx_Timestamp']
                                with open("./xmr_report_ring_members_freq_" + addr + ".csv", "r") as fp3:
                                    next(fp3)  # Skip header of csv
                                    for line3 in fp3:
                                        ring_member_freq_csv_values = line3.split(",")
                                        #  Check if the ring members public key matches the current public key
                                        if data[xmr2csv_report_csv_values[2].strip()]['Output_Pub_Key'] == ring_member_freq_csv_values[0].strip():
                                            #  Add the amount of times it has been seen on chain
                                            Ring_Member['Ring_Member_Freq'] = int(ring_member_freq_csv_values[1].strip())
                                data[xmr2csv_report_csv_values[2].strip()]['Ring_Members_OnChain'].append(Ring_Member)

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
                    transaction['Tx_Timestamp'] = xmr2csv_outgoing_csv_values[0].strip()
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
