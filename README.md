# AI Expense Claim for ERPNext

<p align="center">
  Add receipt processing to ERPNext Expense Claims. Extract expense details with AI, review them, and apply them to a claim.
</p>

<p align="center">
  <a href="https://github.com/stymrj/ai-expense-claim/stargazers"><img alt="GitHub stars" src="https://img.shields.io/github/stars/stymrj/ai-expense-claim?style=flat-square"></a>
  <img alt="Frappe v15 and v16" src="https://img.shields.io/badge/Frappe-v15%20%7C%20v16-blue?style=flat-square">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square">
  <a href="license.txt"><img alt="MIT License" src="https://img.shields.io/badge/License-MIT-green?style=flat-square"></a>
</p>

> **AI-assisted, not automatic approval.** Review extracted information before applying it to an expense claim.

## Contents

- [Features](#features)
- [Demo](#demo)
- [Requirements](#requirements)
- [Install](#install)
- [Configure](#configure)
- [Use it](#use-it)
- [How processing works](#how-processing-works)
- [Privacy and security](#privacy-and-security)
- [Mobile use](#mobile-use)
- [Contributing](#contributing)
- [License](#license)

## Features

- **Receipt extraction:** extract dates, amounts, expense types, and descriptions using OpenAI.
- **Common receipt formats:** upload PDF, JPG, PNG, or WEBP files.
- **Batch processing:** process multiple receipts in one session.
- **Review before applying:** inspect extracted values and attachments before adding expense rows.
- **Expense grouping:** optionally combine same-date, same-type expenses.
- **Payment-proof matching:** optionally merge matching payment screenshots with bills using an amount tolerance.
- **Confidence checks:** flag documents that do not meet the configured confidence threshold.
- **Attachment privacy:** choose whether processed files are stored as private attachments.

## Demo

[Watch the demo video](https://github.com/user-attachments/assets/e6fe0cf7-9f9a-45c9-836d-a50048c627b1).

## Requirements

- Frappe **v15 or v16**
- ERPNext/HRMS installed with the **Expense Claim** and **Expense Claim Type** DocTypes
- Python **3.10 or later**
- An OpenAI API key
- Poppler utilities for scanned-PDF image conversion (for example, `poppler-utils` on Ubuntu)

## Install

Back up your site and test the app on a staging site before installing it in production.

Run these commands from your Frappe bench:

```bash
bench get-app https://github.com/stymrj/ai-expense-claim.git --branch main
bench setup requirements
bench --site <your-site-name> install-app ai_expense_claim
bench build --app ai_expense_claim
bench restart
```

On Ubuntu, install Poppler if it is not already available:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils
```

## Configure

1. In ERPNext, use the search bar to open **AI Expense Settings**.
2. Enter your OpenAI API key and choose a model (`gpt-4o` or `gpt-4o-mini`).
3. Set the minimum confidence threshold. The default is **85**.
4. Choose whether AI-processed attachments should be private.
5. Optionally enable same-date/type grouping or payment-proof matching. Set the amount tolerance when matching is enabled.

The app uses the Expense Claim Types configured in your ERPNext site. On installation, it adds default types for Food, Travel, Accommodation, Fuel, and Communication when they do not already exist.

## Use it

1. Create or open a draft **Expense Claim**.
2. Select **Upload & Process AI-Based Bills**.
3. Choose or drop receipt images and PDFs.
4. Select **Process with AI**.
5. Review the extracted values, correct anything needed, and apply the selected rows to the claim.
6. Save and submit the claim through your normal ERPNext approval workflow.

The app does not automatically submit or approve claims.

## How processing works

1. The uploaded documents are sent to the app's server-side processing endpoint.
2. The app extracts text from PDFs and uses image processing for image receipts and scanned PDFs.
3. Extracted expense types are matched against the site's Expense Claim Types.
4. Low-confidence documents are reported for review.
5. Selected results and attachments are added to the open claim.

## Privacy and security

- Receipt contents are sent to OpenAI for extraction. Confirm that this is permitted by your organization's data policies before use.
- Enter the API key only in **AI Expense Settings**. Do not commit keys to source code or include them in a mobile or browser client.
- Private attachment storage is configurable and is not enabled by default.
- AI extraction can be incorrect. Verify dates, expense types, descriptions, and amounts before submitting a claim.

## Mobile use

Use the ERPNext site in a supported mobile browser, sign in, and open an Expense Claim. The upload dialog accepts images and PDFs from the device. This repository provides an ERPNext feature, not a standalone Android or iOS app.

## Contributing

Issues and pull requests are welcome. When contributing, describe the change and how you tested it. Preserve existing license and author notices when redistributing or modifying the project.

## License

Distributed under the [MIT License](license.txt).
