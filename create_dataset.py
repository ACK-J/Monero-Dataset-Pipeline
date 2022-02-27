import os
import pickle
import time
import requests
# find last directories
# Combine 5 files
# Enrich data
# Add to final dataset

# TODO add checkpoint saves
# TODO add tx inputs and decoy info

# Key = tx hash, val = dict(transaction metadata)
data = {}
API_URL = "https://melo.tools/explorer/testnet/api"


def enrich_data():
    for txid in data.keys():
        try:
            tx_response = requests.get(API_URL + "/transaction/" + str(txid)).json()["data"]
            block_response = requests.get(API_URL + "/block/" + str(tx_response["block_height"])).json()["data"]
            previous_block_response = requests.get(API_URL + "/block/" + str(int(tx_response["block_height"]) - 1)).json()["data"]
            data[txid]['Tx_Size'] = tx_response["tx_size"]
            data[txid]['Tx_Fee_Per_Byte'] = float(data[txid]['Tx_Fee']) / int(data[txid]['Tx_Size'])
            data[txid]['Tx_Timestamp_Epoch'] = tx_response["timestamp"]
            data[txid]['Num_Confirmations'] = tx_response["confirmations"]
            data[txid]['Time_Of_Enrichment'] = time.time()
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
            data[txid]['Total_Block_Fee'] = total_block_fee
            data[txid]['Block_Size'] = block_response["size"]
            data[txid]['Time_Since_Last_Block'] = int(block_response["timestamp"]) - int(previous_block_response["timestamp"])
        except Exception as e:
            pass


def combine_files(Wallet_addrs):
    for addr in Wallet_addrs:
        with open("./cli_export_" + addr + ".csv", "r") as fp:
            next(fp)  # Skip header of csv
            for line in fp:
                values = line.split(",")
                if values[1].strip() == "out":
                    transaction = {}
                    transaction['Tx_Hash'] = values[6].strip()
                    transaction['Block_Number'] = int(values[0].strip())
                    transaction['Direction'] = values[1].strip()
                    transaction['Tx_Timestamp'] = values[3].strip()
                    transaction['Amount'] = float(values[4].strip())
                    transaction['Wallet_Balance'] = float(values[5].strip())
                    transaction['Tx_Fee'] = values[8].strip()
                    transaction['Destination_Address'] = values[9].strip()

                    with open("./xmr2csv_start_time_" + addr + ".csv", "r") as fp:
                        for line in fp:
                            transaction['xmr2csv_Data_Collection_Time'] = line

                    if transaction['Tx_Hash'] not in data:
                        data[transaction['Tx_Hash']] = transaction

        with open("./xmr_report_" + addr + ".csv", "r") as fp:
            next(fp)  # Skip header of csv
            for line in fp:
                values = line.split(",")
                if values[2].strip() in data:
                    data[values[2].strip()]['Tx_Version'] = values[4].strip()
                    data[values[2].strip()]['Tx_Public_Key'] = values[3].strip()
                    data[values[2].strip()]['Output_Pub_Key'] = values[8].strip()
                    data[values[2].strip()]['Output_Key_Img'] = values[9].strip()
                    data[values[2].strip()]['Output_Number_Spent'] = values[10].strip()
                else:
                    transaction = {}
                    transaction['Tx_Hash'] = values[2].strip()
                    transaction['Tx_Version'] = values[4].strip()
                    transaction['Tx_Public_Key'] = values[3].strip()
                    transaction['Output_Pub_Key'] = values[8].strip()
                    transaction['Output_Key_Img'] = values[9].strip()
                    transaction['Output_Number_Spent'] = values[10].strip()
                    with open("./xmr2csv_start_time_" + addr + ".csv", "r") as fp:
                        for line in fp:
                            transaction['xmr2csv_Data_Collection_Time'] = line
                    data[values[2].strip()] = transaction

        with open("./xmr_report_outgoing_txs_" + addr + ".csv", "r") as fp:
            next(fp)  # Skip header of csv
            for line in fp:
                values = line.split(",")
                if values[2].strip() in data:
                    data[values[2].strip()]['Ring_no/Ring_size'] = values[5].strip()
                else:
                    transaction = {}
                    transaction['Tx_Hash'] = values[2].strip()
                    transaction['Tx_Timestamp'] = values[0].strip()
                    transaction['Block_Number'] = values[1].strip()
                    transaction['Output_Pub_Key'] = values[3].strip()
                    transaction['Output_Key_Img'] = values[4].strip()
                    transaction['Ring_no/Ring_size'] = values[5].strip()
                    with open("./xmr2csv_start_time_" + addr + ".csv", "r") as fp:
                        for line in fp:
                            transaction['xmr2csv_Data_Collection_Time'] = line
                    data[values[2].strip()] = transaction

        # with open("./xmr_report_ring_members_" + addr + ".csv", "r") as fp:
        #     next(fp)  # Skip header of csv
        #     for line in fp:
        #         values = line.split(",")
        #         if values[2].strip() in data:
        #             data[values[2].strip()]['Ring_no/Ring_size'] = values[5].strip()
        #         else:
        #             transaction = {}
        #             transaction['Tx_Hash'] = values[2].strip()
        #             transaction['Tx_Timestamp'] = values[0].strip()
        #             transaction['Block_Number'] = values[1].strip()
        #             transaction['Output_Pub_Key'] = values[3].strip()
        #             transaction['Output_Key_Img'] = values[4].strip()
        #             transaction['Ring_no/Ring_size'] = values[5].strip()
        #             with open("./xmr2csv_start_time_" + addr + ".csv", "r") as fp:
        #                 for line in fp:
        #                     transaction['xmr2csv_Data_Collection_Time'] = line
        #             data[values[2].strip()] = transaction

        # with open("./xmr_report_ring_members_freq_" + addr + ".csv", "r") as fp:
        #     next(fp)  # Skip header of csv
        #     for line in fp:
        #         values = line.split(",")
        #         if values[2].strip() in data:
        #             data[values[2].strip()]['Ring_no/Ring_size'] = values[5].strip()
        #         else:
        #             transaction = {}
        #             transaction['Tx_Hash'] = values[2].strip()
        #             transaction['Tx_Timestamp'] = values[0].strip()
        #             transaction['Block_Number'] = values[1].strip()
        #             transaction['Output_Pub_Key'] = values[3].strip()
        #             transaction['Output_Key_Img'] = values[4].strip()
        #             transaction['Ring_no/Ring_size'] = values[5].strip()
        #             data[values[2].strip()] = transaction
        #             with open("./xmr2csv_start_time_" + addr + ".csv", "r") as fp:
        #                 for line in fp:
        #                     transaction['xmr2csv_Data_Collection_Time'] = line



def discover_wallet_directories():
    # traverse root directory, and list directories as dirs and files as files
    unique_directories = []
    for root, dirs, files in os.walk("./Wallets"):
        for name in files:
            if name.lower().endswith(".csv"):
                if root not in unique_directories:
                    unique_directories.append(root)
    print(unique_directories)
    cwd = os.getcwd()
    for dir in unique_directories:
        os.chdir(dir)
        Wallet_addrs = []
        for root, dirs, files in os.walk("."):
            for name in files:
                if name.lower().endswith(".csv"):
                    addr = name[::-1].split(".")[1].split("_")[0][::-1]
                    if addr not in Wallet_addrs:
                        Wallet_addrs.append(addr)
            combine_files(Wallet_addrs)
        print(Wallet_addrs)
        os.chdir(cwd)


def main():
    discover_wallet_directories()
    enrich_data()
    with open("data.pkl", "wb") as fp:
        pickle.dump(data, fp)

    # with open("data.pkl", "rb") as fp:
    #     data = pickle.load(fp)


if __name__ == '__main__':
    main()
